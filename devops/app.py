from aws_cdk import (
    Stack,
    Duration,
    App,
    RemovalPolicy,
    aws_ecr,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
)
from constructs import Construct
import os
from os import getenv

AWS_TARGET_ACCOUNT = getenv('AWS_TARGET_ACCOUNT')
LAMBDA_CODE_IMAGE_TAG = getenv('LAMBDA_CODE_IMAGE_TAG')
ECR_REPOSITORY = getenv('ECR_REPOSITORY')
AWS_REGION = getenv('AWS_REGION')
API_KEY = getenv('API_KEY')
API_NAME = getenv('API_NAME')
STACK_NAME = getenv('STACK_NAME')
TABLE_NAME = getenv('TABLE_NAME')
BEDROCK_MODEL = getenv('BEDROCK_MODEL')
lambda_code_image_repository =  f"arn:aws:ecr:{AWS_REGION}:{AWS_TARGET_ACCOUNT}:repository/{ECR_REPOSITORY}"


class IncidentAlertStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # DynamoDB Table
        table = dynamodb.Table(
            self, "IncidentAlerts",
            table_name=TABLE_NAME,
            partition_key=dynamodb.Attribute(
                name="incident_id", type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
        )

        ecr_repository = aws_ecr.Repository.from_repository_arn(
                self, 'EiaECRepository', repository_arn=lambda_code_image_repository)

        Code=_lambda.Code.from_ecr_image(
            repository=ecr_repository,
            tag_or_digest=LAMBDA_CODE_IMAGE_TAG
        )

        # IAM Role for Lambda
        lambda_role = iam.Role(
            self, "IncidentHandlerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "DynamoDBAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "dynamodb:PutItem",
                                "dynamodb:GetItem",
                                "dynamodb:UpdateItem",
                                "dynamodb:DeleteItem",
                                "dynamodb:Query",
                                "dynamodb:Scan"
                            ],
                            resources=[table.table_arn]
                        )
                    ]
                ),
                "BedrockAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["bedrock:*"],
                            resources=["*"]
                        )
                    ]
                ),
                "APIGatewayAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["execute-api:*"],
                            resources=["*"]
                        )
                    ]
                )
            }
        )

        # Lambda Function
        fn = _lambda.Function(
            self, "IncidentHandler",
            runtime=_lambda.Runtime.FROM_IMAGE,
            handler=_lambda.Handler.FROM_IMAGE,
            code=Code,
            role=lambda_role,
            function_name="incident-alert",
            memory_size=1024,
            environment={
                "TABLE_NAME": table.table_name,
                "API_KEY": API_KEY,
                "API_NAME": API_NAME,
                "BEDROCK_MODEL": BEDROCK_MODEL,
            },
            timeout=Duration.seconds(900)
        )

        cors_options = apigateway.CorsOptions(
            allow_origins=apigateway.Cors.ALL_ORIGINS,
            allow_credentials=True,
            allow_headers=apigateway.Cors.DEFAULT_HEADERS,
            allow_methods=apigateway.Cors.ALL_METHODS,
        )

        rest_api_stage_options = apigateway.StageOptions(
            caching_enabled=False,
            data_trace_enabled=False,
            logging_level=apigateway.MethodLoggingLevel.ERROR,
            metrics_enabled=False,
            throttling_burst_limit=None,
            throttling_rate_limit=None,
            access_log_destination=None,
            access_log_format=None,
            cache_cluster_enabled=False,
            stage_name="api",
            tracing_enabled=True,
        )

        _ = apigateway.LambdaRestApi(
            self,
            "RestAPIGateway",
            handler=fn,
            proxy=True,
            description="Incident API Service",
            minimum_compression_size=2500,
            rest_api_name=API_NAME,
            default_cors_preflight_options=cors_options,
            deploy=True,
            deploy_options=rest_api_stage_options,
            endpoint_types=[apigateway.EndpointType.REGIONAL],
            integration_options=apigateway.LambdaIntegrationOptions(
                timeout=Duration.seconds(29)
            )
        )


app = App()
IncidentAlertStack(app, STACK_NAME)

app.synth()