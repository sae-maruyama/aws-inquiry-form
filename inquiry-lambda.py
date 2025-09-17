import json
import boto3
import uuid
import os
from datetime import datetime

# ハンドラー外でDynamoDBリソースを初期化（パフォーマンス向上）
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_NAME', 'InquiryTable')
table = dynamodb.Table(table_name)

def lambda_handler(event, context):
    # CORS用の共通ヘッダー（環境変数化）
    cors_headers = {
        'Access-Control-Allow-Origin': os.environ.get('CORS_ORIGIN', 'https://xxxx.com')
    }
    
    # API Gateway経由の場合、bodyをパース
    if 'body' in event and event['body']:
        try:
            # bodyが文字列の場合（API Gateway）
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Invalid JSON format'})
            }
    else:
        # 直接呼び出しの場合
        body = event

    # 1. 入力パラメータのチェック
    required_fields = ["mailAddress", "userName", "reviewText"]
    missing_fields = [field for field in required_fields if field not in body or not body[field]]

    if missing_fields:
        return {
            'statusCode': 400,
            'headers': cors_headers,
            'body': json.dumps({
                'error': 'Validation failed',
                'missing_fields': missing_fields
            })
        }
    
    # 2.入力パラメータの取得
    mailAddress = body["mailAddress"]
    userName = body["userName"]
    reviewText = body["reviewText"]
    
    # 3.idの生成（uuidを取得）
    item_id = str(uuid.uuid4())
    
    # 4.タイムスタンプの取得
    timestamp = datetime.now().isoformat()
    
    # 5.DynamoDBに更新するitemの内容を辞書で定義
    item = {
        'id': item_id,
        'mailAddress': mailAddress,
        'userName': userName,
        'reviewText': reviewText,
        'createdAt': timestamp,
        'updatedAt': timestamp
    }
    
    try:
        # 6.DynamoDBにデータを保存
        table.put_item(Item=item)
    except Exception as e:
        # 7.エラーが発生した場合、ステータスコード500（内部サーバエラー）を返す
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': f'Error saving item to DynamoDB: {str(e)}'})
        }
    
    # 8.ステータスコード200（正常終了）を返す
    return {
        'statusCode': 200,
        'headers': cors_headers,
        'body': json.dumps({
            'message': 'Inquiry saved successfully!'
        })
    }