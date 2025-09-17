# AWS サーバーレス お問い合わせフォーム

AWS サービスを使用したサーバーレスお問い合わせフォーム: S3 + CloudFront + API Gateway + Lambda + DynamoDB

## システム構成

```
Webフォーム (S3 + CloudFront) → API Gateway → Lambda → DynamoDB
https://blue-bird.blog         https://xxxxx.execute-api.us-east-1.amazonaws.com/dev
```

## 前提条件

- AWS アカウント
- 取得済みドメイン（例：お名前.com で取得した blue-bird.blog）

## CORS と CSP について

### CORS（Cross-Origin Resource Sharing）とは
- **目的**: 異なるドメイン間での通信を許可する仕組み
- **必要な理由**: `https://blue-bird.blog`（フォーム）から `https://api-gateway-url`（API）への通信は異なるオリジン間のため、ブラウザが標準でブロックする
- **設定方法**: サーバー側（Lambda）がレスポンスヘッダーで「このドメインからのアクセスを許可する」と宣言

### CSP（Content Security Policy）とは
- **目的**: XSS攻撃などのセキュリティリスクを防ぐ
- **必要性**: なくても動作するが、セキュリティ向上のため推奨
- **設定方法**: HTML側でメタタグにより「このページはどこへのリクエストを許可するか」を制限

## セットアップ手順

### 1. DynamoDB テーブル作成

1. **DynamoDB コンソール**で「テーブルの作成」
2. **テーブル名**: `InquiryTable`
3. **パーティションキー**: `id` (String)
4. その他はデフォルト設定で作成

### 2. Lambda 関数作成

1. **Lambda コンソール**で「関数の作成」
2. **関数名**: `UploadInquiry`
3. **ランタイム**: Python 3.9 以上
4. **実行ロール**: DynamoDB への読み書き権限を追加

**Lambda コード**:
```python
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
        'Access-Control-Allow-Origin': os.environ.get('CORS_ORIGIN', 'https://blue-bird.blog')
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
            'message': 'Inquiry saved successfully!',
            'id': item_id
        })
    }
```

5. **環境変数の設定**（重要：CORS設定）:
   - `TABLE_NAME`: `InquiryTable`
   - `CORS_ORIGIN`: `https://blue-bird.blog`（実際のドメインに変更）

**CORS設定のポイント**: 
- すべての `return` 文に `headers: cors_headers` を含める
- 環境変数で簡単にドメインを変更可能
- Lambda プロキシ統合では、API Gateway側ではなくLambda側でCORSを制御

### 3. API Gateway 作成

1. **API Gateway コンソール**で「REST API」を作成
2. **API 名**: `blue-bird-blog-api`
3. **リソース**:
   - ルートリソース（/）に **POST メソッド**を作成
   - **統合タイプ**: Lambda プロキシ統合
   - **Lambda 関数**: `UploadInquiry`を選択
4. **デプロイ**: ステージ名 `dev` で API をデプロイ
5. **呼び出し URL をメモ**: `https://xxxxxxxxxx.execute-api.region.amazonaws.com/dev`

**注意**: OPTIONSメソッドは不要です。Lambdaプロキシ統合では実際のPOSTリクエストでCORS処理を行います。

### 4. S3 バケット作成

1. **S3 コンソール**でバケット作成
2. **静的ウェブサイトホスティング**を有効化
3. **インデックスドキュメント**: `index.html`
4. **パブリック読み取りアクセス**を許可

### 5. HTML フォーム作成

**index.html**:
```html
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>お問い合わせフォーム</title>
    <!-- CSP設定: セキュリティ向上のため（削除しても動作する） -->
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self' https://xxxxxxxxxx.execute-api.region.amazonaws.com;">
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }
        .form-group { margin-bottom: 1rem; }
        label { display: block; margin-bottom: 0.3rem; font-weight: bold; }
        input, textarea { width: 100%; padding: 0.5rem; font-size: 1rem; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }
        .required { color: red; font-size: 0.9rem; }
        button { background-color: #0073e6; color: white; padding: 0.6rem 1.2rem; font-size: 1rem; border: none; border-radius: 6px; cursor: pointer; }
        button:hover { background-color: #005bb5; }
        button:disabled { background-color: #ccc; cursor: not-allowed; }
    </style>
</head>
<body>
    <h1>お問い合わせフォーム</h1>
    <form id="inquiryForm">
        <div class="form-group">
            <label for="userName">お名前 <span class="required">※必須</span></label>
            <input type="text" id="userName" name="userName" autocomplete="name" required>
        </div>
        <div class="form-group">
            <label for="mailAddress">メールアドレス <span class="required">※必須</span></label>
            <input type="email" id="mailAddress" name="mailAddress" autocomplete="email" inputmode="email" required>
        </div>
        <div class="form-group">
            <label for="reviewText">お問い合わせ内容 <span class="required">※必須</span></label>
            <textarea id="reviewText" name="reviewText" rows="5" required></textarea>
        </div>
        <button type="submit">送信</button>
    </form>

    <script>
        document.addEventListener('DOMContentLoaded', function () {
            document.getElementById('inquiryForm').addEventListener('submit', function (e) {
                e.preventDefault();
                
                const button = this.querySelector('button[type="submit"]');
                const originalText = button.textContent;
                button.textContent = '送信中...';
                button.disabled = true;

                const formData = {
                    userName: document.getElementById('userName').value,
                    mailAddress: document.getElementById('mailAddress').value,
                    reviewText: document.getElementById('reviewText').value
                };

                fetch('https://xxxxxxxxxx.execute-api.region.amazonaws.com/dev', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                })
                .then(response => response.json())
                .then(result => {
                    if (result.message) {
                        alert('お問い合わせを送信しました！ID: ' + result.id);
                        this.reset();
                    } else {
                        throw new Error(result.error || 'エラーが発生しました');
                    }
                })
                .catch(error => {
                    alert('送信に失敗しました: ' + error.message);
                    console.error('Error:', error);
                })
                .finally(() => {
                    button.textContent = originalText;
                    button.disabled = false;
                });
            });
        });
    </script>
</body>
</html>
```

**重要な置き換え箇所**:
- `https://xxxxxxxxxx.execute-api.region.amazonaws.com` を実際の API Gateway URL に置き換える（2箇所）

**CSP設定のポイント**:
- `connect-src` に API Gateway URL を追加
- セキュリティ向上のため推奨だが、削除しても動作する

### 6. CloudFront Distribution 作成

1. **CloudFront コンソール**で Distribution 作成
2. **オリジンドメイン**: S3 バケットの**ウェブサイトエンドポイント**を使用
3. **SSL 証明書**: ACM で証明書を取得（**US East 1 リージョン**で作成）
4. **CNAME**: カスタムドメイン名（blue-bird.blog）を追加

### 7. Route53 設定

1. **Route53 コンソール**でホストゾーン作成
2. **ドメイン名**: blue-bird.blog
3. **A レコード作成**:
   - **名前**: blue-bird.blog
   - **エイリアス**: はい
   - **エイリアス先**: CloudFront Distribution
4. **お名前.com 設定**: ネームサーバーを Route53 のものに変更

## CORS と CSP の動作確認

### リクエストの流れ
1. ユーザーが `https://blue-bird.blog` でフォーム送信
2. **CSP チェック**: ブラウザが「connect-src」設定を確認し、API Gateway への接続を許可
3. **JavaScript実行**: `fetch()` で API Gateway にPOSTリクエスト送信
4. **CORS チェック**: Lambda が `Access-Control-Allow-Origin` ヘッダーを付けてレスポンス
5. **成功**: ブラウザがレスポンスを JavaScript に渡す

### 設定箇所まとめ
- **CORS**: Lambda コード内の `cors_headers` + 環境変数 `CORS_ORIGIN`
- **CSP**: HTML の `<meta>` タグ内の `connect-src`

## テスト・デバッグ

### 動作確認手順
1. `https://blue-bird.blog` でフォームにアクセス
2. 全項目入力して送信
3. 成功メッセージとID表示を確認
4. DynamoDB テーブルでデータ保存確認

### よくある問題

| 問題 | 原因 | 解決方法 |
|------|------|----------|
| CORS エラー | Lambda の CORS_ORIGIN 環境変数未設定 | 環境変数を確認 |
| JavaScript が動作しない | キャッシュまたはCSPエラー | CloudFront無効化、ブラウザ強制リフレッシュ |
| API が見つからない | API Gateway URL 間違い | ステージの呼び出し URL を再確認 |
| フォームが通常送信される | JavaScript エラー | ブラウザコンソールでエラー確認 |

### デバッグ方法
- **ブラウザ**: F12 で Console と Network タブを確認
- **Lambda**: CloudWatch Logs でエラー確認
- **CORS確認**: Network タブでレスポンスヘッダーを確認

## セキュリティ・運用考慮事項

- HTTPS のみ使用
- IAM ロールは最小権限設定
- CloudWatch でモニタリング設定
- 定期的なセキュリティ更新

## コスト最適化

- DynamoDB オンデマンド料金（低トラフィック向け）
- Lambda 実行時間の最適化
- CloudWatch ログの保持期間設定

---

このシステムにより、スケーラブルで実用的なお問い合わせフォームが完成します。CORS設定により異なるドメイン間通信が可能になり、CSP設定でセキュリティも向上します。