package main

import (
	"time"
	"strconv"
	"encoding/json"
	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/dynamodb"
	"github.com/aws/aws-sdk-go/service/dynamodb/dynamodbattribute"
	"crypto/md5"
	"encoding/hex"
	"log"
)

func CacheConnect(region string) (*dynamodb.DynamoDB) {
	awscfg := &aws.Config{}
	awscfg.WithRegion("us-west-2")

	// Create the session that the DynamoDB service will use.
	sess := session.Must(session.NewSession(awscfg))

	// Create the DynamoDB service client to make the query request with.
	return dynamodb.New(sess)
}

func CachePut(db *dynamodb.DynamoDB, table_name string, key string, value string) (err error) {
	var input = &dynamodb.PutItemInput{
		Item: map[string]*dynamodb.AttributeValue{
			"key": {
				S: aws.String(key),
			},
			"value": {
				S: aws.String(value),
			},
			"creation_time": {
				N: aws.String(strconv.Itoa(int(time.Now().Unix()))),
			},

		},
		TableName: aws.String(table_name),
	}
	_, err = db.PutItem(input)
	return
}

func CacheGet(db *dynamodb.DynamoDB, table_name string, key string) (result string, creation_time int, err error) {
	var input = &dynamodb.GetItemInput{
		Key: map[string]*dynamodb.AttributeValue{
			"key": {
				S: aws.String(key),
			},
		},
		TableName: aws.String(table_name),
	}
	if output, err := db.GetItem(input); err == nil {
		if _, ok := output.Item["value"]; ok {
			dynamodbattribute.Unmarshal(output.Item["value"], &result)
		}
		if _, ok := output.Item["creation_time"]; ok {
			dynamodbattribute.Unmarshal(output.Item["creation_time"], &creation_time)
		}
	}
	return
}

func TryRequestCache(model string, method string, body []byte) (res map[string]interface{}, cache_time int, err error){
	key := CacheKey(model, method, body)
	resp, t, err := CacheGet(cache_db, cache_table_name, key)
	log.Println("Try request cache " + key)
	if err != nil {
		return nil, t, err
	}
	err = json.Unmarshal([]byte(resp), &res)
	log.Println("Try request cache 2")
	log.Println(string(resp))
	log.Println(res, err)
	if err != nil {
		return nil, t, err
	}
	return res, t, err
}

func CacheKey(model string, method string, body []byte) string{
	hasher := md5.New()
	hasher.Write(body)
	hash := hex.EncodeToString(hasher.Sum(nil))
	log.Println("Generating cache key " + model + method + hash)
	return model + method + hash
}
func PutRequestCache(model string, method string, body []byte, response interface{}) error {
	j,_ := json.Marshal(response)
	key := CacheKey(model, method, body)
	log.Println("Put request cache " + key)
	log.Println("Put request with string " + string(j))
	log.Println(cache_db, cache_table_name)
	res := CachePut(cache_db, cache_table_name, key, string(j))
	log.Println(res)
	return res
}
