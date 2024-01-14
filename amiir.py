import boto3
DYNAMO_TABLE = 'AmirAWSpro'
REGION_NAME = 'eu-north-1'


dynamodb = boto3.resource('dynamodb', region_name=REGION_NAME)
table = dynamodb.Table(DYNAMO_TABLE)

response = table.get_item(
        Key={
        'prediction_id': '3445d200-b9e4-460f-aecb-9184e285e3b4',
        'chat_id': '985756940'
    }, TableName = DYNAMO_TABLE
    )

item = response
print(item)