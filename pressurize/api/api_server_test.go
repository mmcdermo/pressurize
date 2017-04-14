package main

import (
	"testing"
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

func TestServer(t *testing.T){
	// NOTE: This test requires TestModel to be deployed to elasticbeanstalk
	// using pressurize.
	go RunServer("./test_data/pressurize.json", "6321")
	result := make(map[string]interface{})

	payload := map[string]int{ "number": 42 }
	url := "http://localhost:6321/api/models/TestModel/predict/"
	t.Log(url)
	err := PerformRequestAndDecode(url, "POST", &payload, &result)

	result_map := result["result"].(map[string]interface{})
	result_num := result_map["number"].(float64)
	if result_num != 43.0 {
		t.Fatal("Incorrect number returned")
	}

	if err != nil {
		t.Fatal(err)
	}
}
