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
	"errors"
	"log"
)

func ConnectDynamo(region string) (*dynamodb.DynamoDB) {
	awscfg := &aws.Config{}
	awscfg.WithRegion("us-west-2")

	// Create the session that the DynamoDB service will use.
	sess := session.Must(session.NewSession(awscfg))

	// Create the DynamoDB service client to make the query request with.
	return dynamodb.New(sess)
}

func CachePut(db *dynamodb.DynamoDB, table_name string, key string, value string, lifetime int) (err error) {
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
			"expires": {
				N: aws.String(strconv.Itoa(int(time.Now().Unix()) + lifetime)),
			},

		},
		TableName: aws.String(table_name),
	}
	_, err = db.PutItem(input)
	return
}

func CacheGet(db *dynamodb.DynamoDB, table_name string, key string) (result string, creation_time int, expires int, err error) {
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
		if _, ok := output.Item["expires"]; ok {
			dynamodbattribute.Unmarshal(output.Item["expires"], &expires)
		} else {
		}
	}
	return
}

func TryRequestCache(model string, method string, body []byte) (res map[string]interface{}, cache_time int, err error){
	key := CacheKey(model, method, body)
	resp, t, expires, err := CacheGet(ddb, cache_table_name, key)
	if err != nil {
		return nil, t, err
	}
	if expires < int(time.Now().Unix()) {
		s := "Cache entry expired at " + strconv.Itoa(expires)
		return nil, t, errors.New(s)
	}
	err = json.Unmarshal([]byte(resp), &res)
	if err != nil {
		return nil, t, err
	}
	return res, t, err
}

func CacheKey(model string, method string, body []byte) string{
	hasher := md5.New()
	hasher.Write(body)
	hash := hex.EncodeToString(hasher.Sum(nil))
	return model + method + hash
}
func PutRequestCache(model string, method string, body []byte, lifetime int, response interface{}) error {
	j,_ := json.Marshal(response)
	key := CacheKey(model, method, body)
	res := CachePut(ddb, cache_table_name, key, string(j), lifetime)
	log.Println(res)
	return res
}
