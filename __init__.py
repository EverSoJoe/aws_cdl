import json
import os
import shutil

import boto3
import botocore

DEFAULT_REGION = 'eu-west-1'

def create_cf_client(profile, region=DEFAULT_REGION):
    '''
    Creates a boto3 cloudformation client with the AWS CLI profile name provided
    '''
    return boto3.Session(profile_name=profile,region_name=region).client('cloudformation')

def create_ssm_secret(profile, name, string, key=None, region=DEFAULT_REGION):
    '''
    Creates a ssm secret with the AWS CLI profile provided.
    If a KMS key is provided the secret will be encrypted.
    '''
    if key:
        boto3.Session(profile_name=profile, region_name=region).client('ssm').put_parameter(
            Name=name,
            Value=string,
            Type='SecureString',
            Overwrite=True,
            KeyId=key
        )
    else:
        boto3.Session(profile_name=profile, region_name=region).client('ssm').put_parameter(
            Name=name,
            Value=string,
            Type='SecureString',
            Overwrite=True
        )

def upload_lambda(profile, folder, bucket, s3key, region=DEFAULT_REGION):
    '''
    Uses AWS CLI profile to check if the specified bucket exists and creates it if not.
    Then it will uploaded the specified folder as zip to that bucket and delete the local zip file.
    '''
    s3 = boto3.Session(profile_name=profile, region_name=region).client('s3')

    try:
        response = s3.head_bucket(Bucket=bucket)
        del response
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            print('Creating bucket %s' %(bucket))
            region = boto3.Session(profile_name=profile).region_name
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={
                    'LocationConstraint': region
                }
            )
        else:
            raise

    print('Making and uploading current state of the Lambda code to %s' %(bucket))
    shutil.make_archive(folder, 'zip', '%s' %(folder))
    s3.upload_file('%s.zip' %(folder), bucket, s3key)
    os.remove('%s.zip' %(folder))

def delete_lambda_package(profile, bucket, s3key, region=DEFAULT_REGION):
    '''
    Deletes the specified S3 object from the specified bucket
    '''
    s3 = boto3.Session(profile_name=profile, region_name=region).client('s3')
    s3.delete_object(
        Bucket=bucket,
        Key=s3key,
    )

def parse_template(client, templateFile):
    '''
    Reads the provided template file, checks its validity and parses it for future use.
    '''
    with open(templateFile) as f:
        template = f.read()
    client.validate_template(TemplateBody=template)
    return template

def stack_exists(client, stackName, force=False):
    '''
    Checks if provided stack exists.
    Will delete stacks in ROLLBACK_COMPLETE state if force parameter is provided.
    '''
    response = client.list_stacks()
    stacks = response['StackSummaries']
    if 'NextToken' in response:
        response = client.list_stacks(NextToken=response['NextToken'])
        stacks = stacks + response['StackSummaries']
    for stack in stacks:
        if stack['StackStatus'] == 'DELETE_COMPLETE':
            continue
        elif stack['StackStatus'] == 'ROLLBACK_COMPLETE':
            if force:
                print('Deleting stack in ROLLBACK_COMPLETE state')
                delete_stack(client, stackName)
                continue
        if stackName == stack['StackName']:
            return True
    return False

def create_update_stack(client, template, parameters, stackName, force):
    '''
    Creates or updates stack with the provided template.
    '''
    templateData = parse_template(client, template)

    params = {
        'StackName': stackName,
        'TemplateBody': templateData,
        'Parameters': parameters,
        'Capabilities': ['CAPABILITY_IAM','CAPABILITY_NAMED_IAM']
    }

    try:
        if stack_exists(client, stackName, force):
            print('Updating %s' %(stackName))
            stackResponse = client.update_stack(**params)
            waiter = client.get_waiter('stack_update_complete')
        else:
            print('Creating %s' %(stackName))
            stackResponse = client.create_stack(**params)
            waiter = client.get_waiter('stack_create_complete')
        print('...waiting for stack to be ready...')
        waiter.wait(StackName=stackName)
    except botocore.exceptions.ClientError as e:
        error_message = e.response['Error']['Message']
        if error_message == 'No updates are to be performed.':
            print('No changes')
        elif 'ROLLBACK_COMPLETE' in error_message:
            exit('Stack is in ROLLBACK_COMPLETE state. Please check the logs, fix the errors and run this tool again with the --force option')
        else:
            raise
    else:
        print(json.dumps(client.describe_stacks(StackName=stackResponse['StackId']), default=str))

def delete_stack(client, stackName):
    '''
    Deletes stack
    '''
    print('Deleting %s' %(stackName))
    if stack_exists(client, stackName):
        client.delete_stack(
            StackName=stackName
        )
        print('...waiting for stack to be deleted...')
        client.get_waiter('stack_delete_complete').wait(StackName=stackName)
    else:
        print('Not stack with that name that can be deleted')