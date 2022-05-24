import os

from aws_cdk import Stack
from aws_cdk import aws_autoscaling as autoscaling
from aws_cdk import aws_ec2 as ec2  # Duration,
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from constructs import Construct


class ArbitrumNodeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        basic_auth_username: str,
        basic_auth_hashed_password: str,
        l1_node_url: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        cluster = ecs.Cluster(self, "ArbitrumNodeCluster", vpc=vpc)

        asg_provider = ecs.AsgCapacityProvider(
            self,
            "ArbitrumNodeAsgCapacityProvider",
            auto_scaling_group=autoscaling.AutoScalingGroup(
                self,
                "ArbitrumNodeAsg",
                instance_type=ec2.InstanceType("i3en.xlarge"),
                vpc=vpc,
                vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
                machine_image=ecs.EcsOptimizedImage.amazon_linux2(),
            ),
        )

        cluster.add_asg_capacity_provider(asg_provider)

        asg_provider.auto_scaling_group.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonSSMManagedInstanceCore"
            )
        )

        asg_provider.auto_scaling_group.connections.allow_from_any_ipv4(
            ec2.Port.tcp(80)
        )
        asg_provider.auto_scaling_group.connections.allow_from_any_ipv4(
            ec2.Port.tcp(443)
        )

        cluster.add_asg_capacity_provider(asg_provider)

        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            *[
                "sudo mkdir /mnt/nvm/",
                "sudo mkfs -t ext4 /dev/nvme1n1",
                "sudo mount -t ext4 /dev/nvme1n1 /mnt/nvm",
                "sudo mkdir -p /mnt/nvm/nodedata",
                "sudo chown ec2-user:ec2-user /mnt/nvm/nodedata",
            ]
        )
        asg_provider.auto_scaling_group.add_user_data(user_data.render())

        log_group = logs.LogGroup(
            self,
            "LogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
        )

        task_definition = ecs.Ec2TaskDefinition(
            self,
            "ArbitrumNodeTaskDefinition",
            network_mode=ecs.NetworkMode.BRIDGE,
            volumes=[
                ecs.Volume(
                    name="nodedata", host=ecs.Host(source_path="/mnt/nvm/nodedata")
                )
            ],
        )

        container = task_definition.add_container(
            "ArbitrumNodeContainer",
            container_name="arbitrum",
            image=ecs.ContainerImage.from_registry(
                "offchainlabs/arb-node:v1.4.0-f4bbe91"
            ),
            memory_reservation_mib=1024,
            logging=ecs.AwsLogDriver(
                log_group=log_group,
                stream_prefix="arbitrum",
                mode=ecs.AwsLogDriverMode.NON_BLOCKING,
            ),
            command=[
                "--l1.url",
                l1_node_url,
                "--core.checkpoint-gas-frequency",
                "156250000",
                "--node.cache.allow-slow-lookup",
                "--node.rpc.tracing.enable",

            ],
            port_mappings=[
                ecs.PortMapping(container_port=8547),  # RPC
                ecs.PortMapping(container_port=8548),  # Websocket
            ],
        )

        container.add_mount_points(
            ecs.MountPoint(
                source_volume="nodedata",
                container_path="/home/user/.arbitrum/mainnet",
                read_only=False,
            )
        )

        caddy_container = task_definition.add_container(
            "CaddyContainer",
            container_name="caddy",
            image=ecs.ContainerImage.from_asset("docker/caddy"),
            memory_reservation_mib=1024,
            logging=ecs.AwsLogDriver(
                log_group=log_group,
                stream_prefix="caddy",
                mode=ecs.AwsLogDriverMode.NON_BLOCKING,
            ),
            port_mappings=[
                ecs.PortMapping(container_port=80, host_port=80),
                ecs.PortMapping(container_port=443, host_port=443),
            ],
            environment={
                "BASICAUTH_USERNAME": basic_auth_username,
                "BASICAUTH_HASHED_PASSWORD": basic_auth_hashed_password,
            },
        )

        caddy_container.add_link(container, "arbitrum")

        service = ecs.Ec2Service(
            self,
            "ArbitrumNodeService",
            cluster=cluster,
            task_definition=task_definition,
        )

        service.task_definition.task_role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "route53:ListResourceRecordSets",
                    "route53:GetChange",
                    "route53:ChangeResourceRecordSets",
                ],
                resources=[
                    "arn:aws:route53:::hostedzone/*",
                    "arn:aws:route53:::change/*",
                ],
            )
        )

        service.task_definition.task_role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=["route53:ListHostedZonesByName", "route53:ListHostedZones"],
                resources=["*"],
            )
        )
