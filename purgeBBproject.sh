#!/bin/bash

username=
password=

if [ -z "$username" -o -z "password" ]; then
	echo 'Please enter your Bitbucket credentials'
	echo 'Username?'
	read username
	echo 'Password?'
	read -s password  # -s flag hides password text	
fi

for repo in `curl -s -X GET -u $username:$password $1 | jq -r '.values[] | .slug'`; do 
	curl -v -X DELETE -u $username:$password $1/$repo; 
done
