package main

import (
	_"flag"
	"net/http"
	"encoding/json"
	"log"
	"os"
	"fmt"
	"io/ioutil"
	"errors"
	"regexp"
	"strings"
	"github.com/gorilla/mux"
	"github.com/aws/aws-sdk-go/service/dynamodb"
)

type Model struct {
	Path string `json:"path"`
	Name string `json:"name"`
	Methods []string `json:"methods"`
	RequiredResources map[string]string `json:"required_resources, omitempty"`
	MinECUPerInstance []string `json:"min_ecu_per_instance,omitempty"`
	MinMemoryPerInstance []string `json:"min_memory_per_instance,omitempty"`
}

type PressurizeConfig struct {
	Models []Model `json:"models"`
	DeploymentName string `json:"deployment_name"`
	AWSRegion string `json:"aws_region"`
}

var (
	config *PressurizeConfig
	models map[string]Model
	cache_db *dynamodb.DynamoDB
	cache_table_name string
	model_host string
)


func ValidModelMethod(model_name string, method_name string) error {
	model, ok := models[model_name]
	if !ok {
		return errors.New("No known model '" + model_name +"'")
	}
	found_method := false
	for _, method := range model.Methods {
		if method_name == method {
			found_method = true
			break
		}
	}
	if !found_method {
		return errors.New("No method '" + method_name +
			"' found for model '"+ model_name +"'.")
	}
	return nil
}

func Sanitize(name string) string {
        reg, err := regexp.Compile("[^A-Za-z0-9]")
	if err != nil {
		log.Fatal(err)
	}
	return reg.ReplaceAllString(name, "")
}

func GetModelURL(model_name string) string {
	if model_host != "" {
		return model_host
	}
	return "http://" + Sanitize(config.DeploymentName) + "-" + model_name + "." +
		config.AWSRegion + ".elasticbeanstalk.com"
}

func GetMethodURL(model_name string, method_name string) string {
	return GetModelURL(model_name) + "/api/" + model_name + "/" + method_name + "/"
}

func ModelInstanceRequest(model_name string, method_name string, data interface{}) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	err := PerformRequestAndDecode(GetMethodURL(model_name, method_name),
		"POST", data, &(result))
	return result, err
}

func CacheBody(body map[string]interface{}) (res []byte, err error){
	exclude := map[string]bool{"user_id": true}

	cleaned := make(map[string]interface{}, 0)
	for k, v := range body {
		if _, ok := exclude[k]; !ok {
			cleaned[k] = v
		}
	}
	res, err = json.Marshal(cleaned)
	return
}
func ModelMethodHandler(w http.ResponseWriter, r *http.Request){
	vars := mux.Vars(r)
	log.Println("Model method handler")
	err := ValidModelMethod(vars["model"], vars["method"])
	if err != nil {
		log.Println("No valid model method")
		m := map[string]string{"error": err.Error()}
		SendResponse(w, 404, m)
		return
	}

	defer r.Body.Close()
	body, err := ioutil.ReadAll(r.Body)
	parsed := make(map[string]interface{})
	err = json.Unmarshal(body, &parsed)
	if err != nil {
		log.Println("Failed to parse payload. Format should be {key: value, key2: value2...}")
		m := map[string]string{"error": err.Error()}
		SendResponse(w, 400, m)
		return
	}

	cache_body, err := CacheBody(parsed)
	if err != nil {
		m := map[string]string{"error": err.Error()}
		SendResponse(w, 500, m)
		return
	}
	cache_result, time, err := TryRequestCache(vars["model"], vars["method"], cache_body)
	if err == nil {
		log.Println("Returning cached response for "+ vars["model"] + "/" + vars["method"])
		m := map[string]interface{}{
			"model": vars["model"],
			"method": vars["method"],
			"from_cache": true,
			"cache_time": time,
			"result": cache_result,
		}
		SendResponse(w, 200, m)
		return
	}


	response, err := ModelInstanceRequest(vars["model"], vars["method"], parsed)
	if err != nil {
		m := map[string]string{"error": err.Error()}
		SendResponse(w, 500, m)
		return
	}

	err_msg, err_exists := response["error"]
	if err_exists {
		m := map[string]string{"error": err_msg.(string)}
		SendResponse(w, 500, m)
		return
	}

	result, result_exists := response["result"]
	if !result_exists {
		m := map[string]string{"error": "Missing result from model server"}
		SendResponse(w, 500, m)
		return
	}

	m := map[string]interface{}{
		"model": vars["model"],
		"method": vars["method"],
		"from_cache": false,
		"cache_time": -1,
		"result": result,
	}
	_ = PutRequestCache(vars["model"], vars["method"], cache_body, result)
	SendResponse(w, 200, m)
	return
}

func loadConfig(path string){
	contents, err := ioutil.ReadFile(path)
	if err != nil {
		fmt.Printf("File error: %v\n", err)
		os.Exit(1)
	}

	err2 := json.Unmarshal(contents, &config)
	if err2 != nil {
		fmt.Printf("Error with config file: %v\n", err2)
		os.Exit(1)
	}

	//Populate models map
	models = make(map[string]Model, len((*config).Models))
	for _, model := range (*config).Models {
		models[model.Name] = model
	}
}

func RunServer(path string, port string, _model_host string){
	loadConfig(path)
	if _model_host != "" {
		model_host = _model_host
	}
	cache_table_name = strings.Replace(config.DeploymentName, "-", "_", -1) + "cache"
	cache_db = CacheConnect(cache_table_name)

	log.Println("Loaded config from " + path)
	r := mux.NewRouter()
	r.HandleFunc("/api/models/{model:[A-Za-z0-9_-]+}/{method:[A-Za-z0-9_-]+}/", ModelMethodHandler)
	http.Handle("/", r)
	log.Println("Running server on port " + port)
	log.Fatal(http.ListenAndServe(":" + port, nil))
}

func main() {
	RunServer("./pressurize.json", "5000", "")
}
