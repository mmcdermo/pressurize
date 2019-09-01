package main
import (
	"log"
	"time"
	"sync"
)

type MethodRequestBatch struct {
	requests []map[string]interface{}
	response_chans []chan map[string]interface{}
	timer *time.Timer
	first_request int64
	last_request int64
	last_setup int64
}
var (
	//
	method_request_batch map[string]map[string]MethodRequestBatch
	batch_lock sync.RWMutex
)

func MethodCanBatch(model string, method string) bool {
	// Methods can batch if there is a corresponding batch_{method} method
	model_config := models[model]
	for _, m := range model_config.Methods {
		if m == "batch_" + method {
			return false
		}
	}
	return true
}

func BatchModelConfig(model_name string) Model {
	model_config := models[model_name]
	if model_config.MaxBatchTime == nil {
		mbt := 1000
		model_config.MaxBatchTime = &mbt
	}
	if model_config.MinBatchTime == nil {
		mbt := 100
		model_config.MinBatchTime = &mbt
	}
	if model_config.MaxBatchSize == nil {
		mbs := 100
		model_config.MaxBatchSize = &mbs
	}
	return model_config
}

func GetBatchMethodURL(model_name string, method_name string) string {
	return GetModelURL(model_name) + "/api/" + model_name + "/" + "batch_" + method_name + "/"
}

func setupMethodRequestBatch(model string, method string){
	last_setup := time.Now().UTC().UnixNano()
	if mrb, ok := method_request_batch[model][method]; ok {
		last_setup = mrb.last_request
	}
	mrb := MethodRequestBatch{
		last_setup: last_setup,
		first_request: time.Now().UTC().UnixNano(),
		last_request: time.Now().UTC().UnixNano(),
		response_chans: make([]chan map[string]interface{}, 0),
		requests: make([]map[string]interface{}, 0),
	}
	method_request_batch[model][method] = mrb
}

func appendMethodRequestBatch(model string, method string, parsed map[string]interface{}) chan map[string]interface{} {
	mrb := method_request_batch[model][method]
	mrb.requests = append(mrb.requests, parsed)
	mrb.last_request = time.Now().UTC().UnixNano()
	new_chan := make(chan map[string]interface{}, 1)
	mrb.response_chans = append(mrb.response_chans, new_chan)
	method_request_batch[model][method] = mrb
	return new_chan
}


func shouldWait(model string, method string) bool {
	mrb := method_request_batch[model][method]
	//return false // TODO
	conf := BatchModelConfig(model)
	if len(mrb.requests) + 1 >= *conf.MaxBatchSize {
		return false
	}
	if len(mrb.requests) == 0 && time.Now().UTC().UnixNano() - mrb.last_setup > int64(*conf.MinBatchTime) * 1000 * 1000 {
		return false
	}
	if time.Now().UTC().UnixNano() - mrb.first_request > int64(*conf.MaxBatchTime * 1000 * 1000) {
		return false
	}
	//if time.Now().UTC().UnixNano() - mrb.last_request < config.Models[model].MinBatchTime {
	//	return true
	//}

	// TODO
	//if len(mrb.requests) == 0 {
	//	return false
	//}
	return true
}

func setupTimer(model string, method string){
	batch_lock.Lock()
	mrb := method_request_batch[model][method]
	if mrb.timer != nil {
		log.Println("Timer already active")
		batch_lock.Unlock()
		return
	}
	//elapsed := time.Now().UTC().UnixNano() - mrb.first_request
	first_request := mrb.first_request
	wait_time := time.Duration(int64(*models[model].MaxBatchTime) * 1000 * 1000)
	mrb.timer = time.NewTimer(wait_time)
	method_request_batch[model][method] = mrb
	log.Println("Timer waiting for", wait_time)
	batch_lock.Unlock()
	<-mrb.timer.C
	batch_lock.Lock()
	log.Println("Timer fired")
	if method_request_batch[model][method].first_request == first_request {
		fireBatchedRequest(model, method)
		setupMethodRequestBatch(model, method)
	} else {
		log.Println("Batch already fired")

	}
	batch_lock.Unlock()
}

func ModelInstanceBatchedRequest(model string, method string, parsed map[string]interface{})  (map[string]interface{}, error){
	batch_lock.Lock()
	var response_chan chan map[string]interface{}
	if method_request_batch == nil {
		method_request_batch = make(map[string]map[string]MethodRequestBatch)
	}
	if _, ok := method_request_batch[model]; !ok {
		method_request_batch[model] = make(map[string]MethodRequestBatch, 0)
	}
	wait := shouldWait(model, method)
	if _, ok := method_request_batch[model][method]; !ok {
		setupMethodRequestBatch(model, method)
	}
	log.Println("About to wait or fire", wait, model, method)
	response_chan = appendMethodRequestBatch(model, method, parsed)
	if wait {
		go setupTimer(model, method)
	} else {
		fireBatchedRequest(model, method)
	}
	batch_lock.Unlock()
	response := <- response_chan
	return response, nil
}


func fireBatchedRequest(model string, method string) (map[string]interface{}, error){
	log.Println("BATCHED REQUEST", model, method)
	mrb := method_request_batch[model][method]
	result := make(map[string]interface{})
	payload := map[string]interface{}{
		"requests": mrb.requests,
	}
	err := PerformRequestAndDecode(GetBatchMethodURL(model, method),
		"POST", payload, &(result))
	result["batched"] = false
	//err := <-ch

	responses := result["responses"].([]interface{})
	log.Println("Number responses", len(responses))
	for i, r := range responses {
		response := r.(map[string]interface{})
		response["batched"] = true
		mrb.response_chans[i] <- response
	}
	setupMethodRequestBatch(model, method)
	return result, err //map[string]interface{}{"result": result}, err
}
