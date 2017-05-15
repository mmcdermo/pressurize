package main

import (
	"time"
	"strconv"
	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/dynamodb"
	"github.com/aws/aws-sdk-go/service/dynamodb/dynamodbattribute"
	_ "log"
	"errors"
)

type AuthToken struct {
	Key string `json:"token"`
	Secret string `json:"secret"`
	Expires int64 `json:"expires,omitempty"`
}

func CreateToken(db *dynamodb.DynamoDB, table_name string, key string, secret string, lifetime int64) (err error) {
	var input = &dynamodb.PutItemInput{
		Item: map[string]*dynamodb.AttributeValue{
			"token_key": {
				S: aws.String(key),
			},
			"secret": {
				S: aws.String(secret),
			},
			"expires": {
				N: aws.String(strconv.FormatInt(int64(time.Now().Unix()) + lifetime, 10)),
			},

		},
		TableName: aws.String(table_name),
	}
	_, err = db.PutItem(input)
	return
}

func TokenLookup(db *dynamodb.DynamoDB, table_name string, token_key string) (token AuthToken, err error) {
	auth_token := AuthToken{Key: token_key}
	var input = &dynamodb.GetItemInput{
		Key: map[string]*dynamodb.AttributeValue{
			"token_key": {
				S: aws.String(token_key),
			},
		},
		TableName: aws.String(table_name),
	}
	if output, err := db.GetItem(input); err == nil {
		if _, ok := output.Item["secret"]; ok {
			dynamodbattribute.Unmarshal(output.Item["secret"], &auth_token.Secret)
		} else {
			return auth_token, errors.New("Failed to unmarshal secret for token " + token_key)
		}
		if _, ok := output.Item["expires"]; ok {
			dynamodbattribute.Unmarshal(output.Item["expires"], &auth_token.Expires)
		} else {
			return auth_token, errors.New("Failed to unmarshal expiry for token " + token_key)
		}
	} else {
		return auth_token, errors.New("Could not find token " + token_key)
	}
	return auth_token, nil
}

func CheckAuth(token_key string, token_secret string) (authed bool, err error){
	token, err := TokenLookup(ddb, auth_table_name, token_key)
	if err != nil {
		return false, err
	}
	if token.Secret == token_secret &&
		token.Expires > int64(time.Now().Unix()) {
		return true, nil
	}
	return false, nil
}
