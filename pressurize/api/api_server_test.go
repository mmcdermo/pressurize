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
	go RunServer("./test_data/pressurize.json", "6321")
	result := make(map[string]interface{})
	payload := map[string]int{ "data": 42 }
	//err := PerformRequestAndDecode("http://localhost:6321/api/test/TestModel/",
	//"POST", &payload, &result)

	url := "http://localhost:6321/api/models/TestModel/predict/"
	url =  "http://pressurizetest-TestModel.us-west-2.elasticbeanstalk.com/api/TestModel/predict/"
	err := PerformRequestAndDecode(url, "POST", &payload, &result)
	if err != nil {
		t.Fatal(err)
	}
}
