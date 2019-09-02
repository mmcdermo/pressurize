package main

import (
	"testing"
	"time"
	"log"
	"math/rand"
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
	db := ConnectDynamo("us-west-2")
	err := CachePut(db, "pressurize_testcache", "testkey", "testvalue", 60)
	if err != nil {
		t.Fatal(err)
	}

	res, cachetime, expires, err := CacheGet(db, "pressurize_testcache", "testkey")
	if res != "testvalue" {
		t.Fatal(err)
	}
	if int(time.Now().Unix()) - cachetime > 5 {
		t.Fatal("Incorrect timestamp on cached data")
	}
	if expires - int(time.Now().Unix()) < 40 ||
		expires - int(time.Now().Unix()) > 60 {
		t.Fatal("Incorrect expiration date on cached data")
	}

}

func TestAuth(t *testing.T){
	db := ConnectDynamo("us-west-2")

	err := CreateToken(db, "pressurize_testauth", "test_token", "mysecret", -400)
	if err != nil {
		t.Fatal(err)
	}
	token, err := TokenLookup(db, "pressurize_testauth", "test_token")
	if err != nil {

		t.Fatal(err)
	}
	if token.Expires > int64(time.Now().Unix()) {
		t.Fatal("Test token should have expired in the past")
	}

	err = CreateToken(db, "pressurize_testauth", "test_token2", "mysecret", 400000)
	if err != nil {
		t.Fatal(err)
	}
	token, err = TokenLookup(db, "pressurize_testauth", "test_token2")
	if err != nil {
		t.Fatal(err)
	}
	if token.Expires < int64(time.Now().Unix()) {
		t.Log(token.Expires)
		t.Fatal("Test token should not yet have expired")
	}
}

func TestServer(t *testing.T){
	// Also requires pressurize_testcache to be a deployed DynamoDB database
	go RunTestModelServer("6500", "TestModel")
	go RunServer("./test_data/pressurize.json", "6321", "http://localhost:6500")
	result := make(map[string]interface{})

	db := ConnectDynamo("us-west-2")
	err := CreateToken(db, "pressurize_testauth", "test_token2", "mysecret", 400000)
	if err != nil {
		t.Fatal(err)
	}
	rand.Seed(time.Now().UTC().UnixNano())
	test_rand := rand.Int()
	log.Println("Test payload:", test_rand)
	payload := map[string]interface{}{
		"user_id": interface{}("2"),
		"data": interface{}(map[string]int{ "number": test_rand }),
		"auth_token_key": "test_token2",
		"auth_secret": "mysecret",
	}
	url := "http://localhost:6321/api/models/TestModel/predict/"
	t.Log(url)
	err = PerformRequestAndDecode(url, "POST", &payload, &result)
	if err != nil {
		t.Fatal(err)
	}


	result_map := result["result"].(map[string]interface{})
	result_num := result_map["number"].(float64)
	if result_num != float64(test_rand) + float64(1.0) {
		t.Fatal("Incorrect number returned")
	}
	if result["from_cache"].(bool) != false {
		t.Fatal("Error: First query should not be cached")
	}
	url = "http://localhost:6321/api/models/TestModel/predict/"
	t.Log(url)

	t.Log("=========== second query ===========")
	err = PerformRequestAndDecode(url, "POST", &payload, &result)
	if err != nil {
		t.Fatal(err)
	}
	t.Log(result)
	if result["from_cache"].(bool) != true {
		t.Fatal("Error: Second Query should be cached")
	}

	t.Log("=========== uncached query ===========")
	payload["no_cache"] = true
	err = PerformRequestAndDecode(url, "POST", &payload, &result)
	if err != nil {
		t.Fatal(err)
	}
	t.Log(result)
	if result["from_cache"].(bool) != false {
		t.Fatal("Error: no_cache parameter should cause result to be uncached")
	}

}


func TestBatch(t *testing.T){
	// NOTE: This test requires TestModel to be running locally @ localhost:6500
	// Also requires pressurize_testcache to be a deployed DynamoDB database

	go RunTestModelServer("6500", "TestModel")
	go RunServer("./test_data/pressurize.json", "6321", "http://localhost:6500")

	db := ConnectDynamo("us-west-2")
	err := CreateToken(db, "pressurize_testauth", "test_token2", "mysecret", 400000)
	if err != nil {
		t.Fatal(err)
	}
	log.Println("Test Batch")
	concurrent_requests := 1
	test_values := make([]int, concurrent_requests)
	results := make([]map[string]interface{}, concurrent_requests)
	result_chan := make([]chan error, 0)
	for _ = range test_values {
		result_chan = append(result_chan, make(chan error))
	}
	rand.Seed(time.Now().UTC().UnixNano())
	log.Println("Test Batch")
	for i := range test_values {
		//time.Sleep(1000 * 1000 * 1000)
		test_values[i] = rand.Int()
		payload := map[string]interface{}{
			"user_id": interface{}("2"),
			"data": interface{}(map[string]int{ "number": test_values[i] }),
			"auth_token_key": "test_token2",
			"auth_secret": "mysecret",
		}
		url := "http://localhost:6321/api/models/TestModel/predict/"
		go PerformAsyncRequest(url, "POST", &payload, &results[i], result_chan[i])
	}
	for i := range test_values {
		err = <- result_chan[i]
		if err != nil {
			t.Fatal(err)
		}
	}

	for i := range test_values {
		result := results[i]
		result_map := result["result"].(map[string]interface{})
		log.Println("Result map", result_map, result)
		result_num := result_map["number"].(float64)
		if result_num != float64(test_values[i]) + float64(1.0) {
			t.Fatal("Incorrect number returned")
		}
		if result["batched"].(bool) == false {
			t.Fatal("Error: All queries should be batched")
		}
	}
}
