import boto3
from utils.utils import generate_filename
from werkzeug.utils import secure_filename
from system.config import S3_KEY, S3_SECRET, S3_BUCKET, S3_LOCATION, DYNAMO_TABLE


s3 = boto3.client(
   "s3",
   aws_access_key_id=S3_KEY,
   aws_secret_access_key=S3_SECRET
)

dynamo = boto3.resource('dynamodb', aws_access_key_id=S3_KEY, aws_secret_access_key=S3_SECRET, region_name='eu-west-2')
table = dynamo.Table(DYNAMO_TABLE)


def upload_file_to_s3(file, content_type=None):
    extension = file.filename.split('.')[-1]
    filename = secure_filename(generate_filename() + '.' + extension)
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    s3.upload_fileobj(file, S3_BUCKET, filename, ExtraArgs={"ACL": "public-read", **extra_args})
    return "{}{}".format(S3_LOCATION, filename)


def insert_dynamo(data: dict):
    table.put_item(Item=data)
