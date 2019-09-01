package main

import (
	_"flag"
	"net/http"
	"encoding/json"
	"log"
	"time"
	"github.com/gorilla/mux"
	"io/ioutil"
)

func BatchTestModelHandler(w http.ResponseWriter, r *http.Request){
	vars := mux.Vars(r)
	log.Println("Batch Test Model method handler for " + vars["model"] + " " + vars["method"])
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
	data := parsed["requests"].([]interface{})
	time.Sleep(1)
	responses := make([]map[string]interface{}, 0)
	for _, d := range data {
		dm := d.(map[string]interface{})
		n := dm["data"].(map[string]interface{})["number"].(float64)
		m := map[string]interface{}{
			"result": map[string]float64{
				"number": n + 1,
			},
		}
		responses = append(responses, m)
	}
	SendResponse(w, 200, map[string]interface{}{"responses": responses})
}


func TestModelHandler(w http.ResponseWriter, r *http.Request){
	vars := mux.Vars(r)
	log.Println("Test Model method handler for " + vars["model"] + " " + vars["method"])
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
	n := parsed["data"].(map[string]interface{})["number"].(float64)
	time.Sleep(1)
	m := map[string]interface{}{
		"result": map[string]float64{
			"number": n + 1,
		},
	}
	SendResponse(w, 200, m)
}


func RunTestModelServer(port string, _model_host string){
	r := mux.NewRouter()
	r.HandleFunc("/api/{model:[A-Za-z0-9_-]+}/batch_{method:[A-Za-z0-9_-]+}/",
		BatchTestModelHandler)
	r.HandleFunc("/api/{model:[A-Za-z0-9_-]+}/{method:[A-Za-z0-9_-]+}/",
		TestModelHandler)
	http.Handle("/api/TestModel/", r)
	log.Println("Running server on port " + port)
	log.Fatal(http.ListenAndServe(":" + port, nil))
}
