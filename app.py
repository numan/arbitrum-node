#!/usr/bin/env python3
import os

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from constructs import Construct

from arbitrum_node.arbitrum_node_stack import ArbitrumNodeStack


class AppStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        vpc_id = os.environ.get("VPC_ID")

        # Create a new vpc if one wasn't provided through environment variables
        if vpc_id is None:
            vpc = ec2.Vpc(
                self,
                "VPC",
                max_azs=2,
                subnet_configuration=[
                    ec2.SubnetConfiguration(
                        cidr_mask=23, name="Public", subnet_type=ec2.SubnetType.PUBLIC
                    )
                ],
            )
        else:
            vpc = ec2.Vpc.from_lookup(self, "VPC", vpc_id=vpc_id)

        CLOUDFLARE_KEY = os.environ.get("CLOUDFLARE_KEY")
        BASICAUTH_USERNAME = os.environ.get("BASICAUTH_USERNAME")
        BASICAUTH_HASHED_PASSWORD = os.environ.get("BASICAUTH_HASHED_PASSWORD")
        L1_NODE_URL = os.environ.get("L1_NODE_URL")

        if CLOUDFLARE_KEY is None:
            raise Exception("CLOUDFLARE_KEY environment variable not set")
        if BASICAUTH_USERNAME is None:
            raise Exception("BASICAUTH_USERNAME environment variable not set")
        if BASICAUTH_HASHED_PASSWORD is None:
            raise Exception("BASICAUTH_HASHED_PASSWORD environment variable not set")
        if L1_NODE_URL is None:
            raise Exception("L1_NODE_URL environment variable not set")

        ArbitrumNodeStack(
            self,
            "ArbitrumNodeStack",
            vpc=vpc,
            cloudflare_key=CLOUDFLARE_KEY,
            basic_auth_username=BASICAUTH_USERNAME,
            basic_auth_hashed_password=BASICAUTH_HASHED_PASSWORD,
            l1_node_url=L1_NODE_URL,
            **kwargs,
        )


app = cdk.App()

environment = cdk.Environment(
    account=os.environ.get("CDK_DEPLOY_ACCOUNT", os.environ["CDK_DEFAULT_ACCOUNT"]),
    region=os.environ.get("CDK_DEPLOY_REGION", os.environ["CDK_DEFAULT_REGION"]),
)
app_stack = AppStack(app, "ArbitrumNodeApp", env=environment)
cdk.Tags.of(app_stack).add("app", "Arbitrum Node")


app.synth()
