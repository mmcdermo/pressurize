package main

import (
	"testing"
	"time"
)


func TestMain(m *testing.M){
	m.Run()
}

func TestLoadConfig(t *testing.T){
	loadConfig("./test_data/pressurize.json")
	if config.DeploymentName != "pressurize-test" {
		t.Fatal("Path incorrect")
	}
	if len(config.Models) != 1 {
		t.Fatal("Incorrect number of models")
	}
	if config.Models[0].Path != "TestModel.TestModel" {
		t.Log(config.Models[0])
		t.Fatal("Path incorrect ", config.Models[0].Path)
	}
}

func TestCache(t *testing.T){
	db := CacheConnect("us-west-2")
	err := CachePut(db, "pressurize_testcache", "testkey", "testvalue")
	if err != nil {
		t.Fatal(err)
	}

	res, cachetime, err := CacheGet(db, "pressurize_testcache", "testkey")
	if res != "testvalue" {
		t.Fatal(err)
	}
	if int(time.Now().Unix()) - cachetime > 5 {
		t.Fatal("Incorrect timestamp on cached data")
	}
}
func TestServer(t *testing.T){
	// NOTE: This test requires TestModel to be running locally @ localhost:6500
	// Also requires pressurize_testcache to be a deployed DynamoDB database
	go RunServer("./test_data/pressurize.json", "6321", "http://localhost:6500")
	result := make(map[string]interface{})

	payload := map[string]interface{}{ "user_id": interface{}("2"),
		"data": interface{}(map[string]int{ "number": 42 })}
	url := "http://localhost:6321/api/models/TestModel/predict/"
	t.Log(url)
	err := PerformRequestAndDecode(url, "POST", &payload, &result)
	if err != nil {
		t.Fatal(err)
	}

	result_map := result["result"].(map[string]interface{})
	result_num := result_map["number"].(float64)
	if result_num != 43.0 {
		t.Fatal("Incorrect number returned")
	}

	// Ensure second request is cached
	payload = map[string]interface{}{ "user_id": interface{}("3"),
		"data": interface{}(map[string]int{ "number": 42 })}
	url = "http://localhost:6321/api/models/TestModel/predict/"
	t.Log(url)
	err = PerformRequestAndDecode(url, "POST", &payload, &result)
	if err != nil {
		t.Fatal(err)
	}
	t.Log(result)
	if result["from_cache"].(bool) != true {
		t.Fatal("Query not cached")
	}
}
