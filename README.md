# **C**loudformation **D**eplyoment **L**ibrary for AWS 

Simple library to make deployment of Cloudformation templates programmatically easier.
It also brings tools to upload and delete AWS Lambda code

## Basic usage
```
import aws_cdl
from datetime import datetime

FORCE = False #Deletes stack first if rollback preceeded this attempt
DELETE_STACK = False
STACK_NAME = 'test-stack'
REGION = 'us-east-1'
PROFILE = 'aws_cli_test_profile'
TEMPLATE_FILE = 'template_path.yaml'
PARAMETERS = [
    {'ParameterKey': 'TestParameter',
     'ParameterValue': 'TestValue'}
]
LAMBDA_FOLDER = 'test-lambda-folder'
S3_BUCKET = 'test-bucket'
S3_KEY = 'test-lambda-%s.zip' %(datetime.now().isoformat) #Time is used for unique key names so lambda is updated with eventual code changes

cfn_client = aws_cdl.create_cf_client(PROFILE, REGION)

if delete_stack:
    aws_cdl.delete_stack(cfn_client, STACK_NAME)
else:
    aws_cdl.upload_lambda_package(PROFILE, LAMBDA_FOLDER, S3_BUCKET, S3_KEY, REGION)
    try:
        aws_cdl.create_update_stack(cfn_client, TEMPLATE_FILE, PARAMETERS, STACK_NAME, FORCE)
    except Exception as e:
        print(e)
    finally:
        aws_cdl.delete_lambda_package(PROFILE, S3_BUCKET, S3_KEY, REGION)
```