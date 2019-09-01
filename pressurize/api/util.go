package main

import (
	"net/http"
	"encoding/json"
	"io/ioutil"
	"strconv"
	"errors"
	"bytes"
	"fmt"
	"log"
)

func SendResponse(w http.ResponseWriter, status_code int, ptr interface{}){
	byteArray, err := json.Marshal(&ptr)
	if err != nil{
		log.Println(err)
		w.WriteHeader(500)
		fmt.Fprint(w, `{"error":"Internal Encoding Error"}`)
		return
	}
	w.WriteHeader(status_code)
	//log.Println(string(byteArray))
	fmt.Fprint(w, string(byteArray))
	return
}

//Perform an HTTP request with the given payload
func PerformRequest(url string, method string, payload interface{}) (*http.Response, error) {
	j,_ := json.Marshal(payload)
	req, err := http.NewRequest(method, url, bytes.NewBuffer(j))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	client := &http.Client{}
	resp, err := client.Do(req)
	return resp, err
}

//Perform an HTTP request with the given payload, decoding the JSON response
func PerformRequestAndDecode(url string, method string, payload interface{},
	decode_target interface{}) error {
	resp, err := PerformRequest(url, method, payload)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	body, err := ioutil.ReadAll(resp.Body)
	if resp.StatusCode > 300 {
		log.Println("Request error body: ", string(body))
		return errors.New("Status returned: " + strconv.Itoa(resp.StatusCode))
	}
	err = json.Unmarshal(body, decode_target)
	if err != nil {
		return err
	}
	return nil
}

func PerformAsyncRequest(url string, method string, payload interface{},
	decode_target interface{}, ch chan error){
	ch <- PerformRequestAndDecode(url, method, payload, decode_target)
}
