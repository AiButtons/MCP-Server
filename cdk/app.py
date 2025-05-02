from aws_cdk import (
    Stack,
    CfnOutput,
    aws_s3_assets as s3_assets,
    App,
    aws_elasticbeanstalk as elasticbeanstalk,
    aws_iam as iam,
)

from constructs import Construct
import os
from config.config_parser import get_config 

config = get_config()

class MCPServerStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        
        # Create IAM role for Elastic Beanstalk service
        eb_service_role = iam.Role(
            self, "PFBM-MCP-ServiceRole",
            assumed_by=iam.ServicePrincipal("elasticbeanstalk.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSElasticBeanstalkService"),
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSElasticBeanstalkEnhancedHealth")
            ]
        )
        
        # Create IAM role for EC2 instances
        ec2_role = iam.Role(
            self, "PFBM-MCP-EC2Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSElasticBeanstalkWebTier"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchLogsFullAccess")
            ]
        )
        
        # Create instance profile
        instance_profile = iam.CfnInstanceProfile(
            self, "PFBM-MCP-InstanceProfile",
            roles=[ec2_role.role_name]
        )
        
        # Create Elastic Beanstalk application
        app = elasticbeanstalk.CfnApplication(
            self, "PFBM-MCP-Application",
            application_name="PFBM-MCP-SERVER"
        )
        
        # Package source code as an S3 Asset
        current_dir = os.path.dirname(os.path.realpath(__file__))
        src_dir = os.path.join(os.path.dirname(current_dir), 'src')  # Point to mcp-server/src
        source_bundle = s3_assets.Asset(
            self, "PFBM-MCP-SourceBundle",
            path=src_dir
        )
        
        # Create application version
        app_version = elasticbeanstalk.CfnApplicationVersion(
            self, "PFBM-MCP-AppVersion",
            application_name=app.application_name,
            source_bundle=elasticbeanstalk.CfnApplicationVersion.SourceBundleProperty(
                s3_bucket=source_bundle.s3_bucket_name,
                s3_key=source_bundle.s3_object_key
            )
        )
        app_version.add_dependency(app)
        
        # Environment variables from config
        is_dev = config.get('deployment', {}).get('ENV', 'dev') == 'dev'
        env_variables = {
            **config.get('clickhouse', {}),
            "ACCESS_TOKEN_SECRET": config.get('SERVICE_SECRETS', {}).get('TEST_ACCESS_TOKEN_SECRET' if is_dev else 'PROD_ACCESS_TOKEN_SECRET', ''),
            "ENV": config.get('deployment', {}).get('ENV', 'dev'),
        }
        
        # Create option settings
        option_settings = [
            elasticbeanstalk.CfnEnvironment.OptionSettingProperty(
                namespace="aws:elasticbeanstalk:environment",
                option_name="EnvironmentType",
                value="LoadBalanced"
            ),
            elasticbeanstalk.CfnEnvironment.OptionSettingProperty(
                namespace="aws:elasticbeanstalk:environment",
                option_name="LoadBalancerType",
                value="application"
            ),
            elasticbeanstalk.CfnEnvironment.OptionSettingProperty(
                namespace="aws:elasticbeanstalk:environment",
                option_name="ServiceRole",
                value=eb_service_role.role_name
            ),
            elasticbeanstalk.CfnEnvironment.OptionSettingProperty(
                namespace="aws:autoscaling:launchconfiguration",
                option_name="IamInstanceProfile",
                value=instance_profile.ref
            ),
            elasticbeanstalk.CfnEnvironment.OptionSettingProperty(
                namespace="aws:autoscaling:launchconfiguration",
                option_name="InstanceType",
                value="t3.large"
            ),
            elasticbeanstalk.CfnEnvironment.OptionSettingProperty(
                namespace="aws:autoscaling:asg",
                option_name="MinSize",
                value="1"
            ),
            elasticbeanstalk.CfnEnvironment.OptionSettingProperty(
                namespace="aws:autoscaling:asg",
                option_name="MaxSize",
                value="4"
            ),
            elasticbeanstalk.CfnEnvironment.OptionSettingProperty(
                namespace="aws:elasticbeanstalk:environment:proxy",
                option_name="ProxyServer",
                value="nginx"
            ),
            elasticbeanstalk.CfnEnvironment.OptionSettingProperty(
                namespace="aws:elasticbeanstalk:application:environment",
                option_name="PORT",
                value="8081"
            ),
            # CloudWatch Logs Configuration
            elasticbeanstalk.CfnEnvironment.OptionSettingProperty(
                namespace="aws:elasticbeanstalk:cloudwatch:logs",
                option_name="StreamLogs",
                value="true"
            ),
            elasticbeanstalk.CfnEnvironment.OptionSettingProperty(
                namespace="aws:elasticbeanstalk:cloudwatch:logs",
                option_name="DeleteOnTerminate",
                value="false"
            ),
            elasticbeanstalk.CfnEnvironment.OptionSettingProperty(
                namespace="aws:elasticbeanstalk:cloudwatch:logs",
                option_name="RetentionInDays",
                value="7"
            ),
            # Enhanced Health Reporting
            elasticbeanstalk.CfnEnvironment.OptionSettingProperty(
                namespace="aws:elasticbeanstalk:healthreporting:system",
                option_name="SystemType",
                value="enhanced"
            ),
        ]
        
        # Add environment variables
        for key, value in env_variables.items():
            if value:
                option_settings.append(
                    elasticbeanstalk.CfnEnvironment.OptionSettingProperty(
                        namespace="aws:elasticbeanstalk:application:environment",
                        option_name=key,
                        value=value
                    )
                )
        
        # Create Elastic Beanstalk environment
        environment = elasticbeanstalk.CfnEnvironment(
            self, "PFBM-MCP-Environment",
            application_name=app.application_name,
            environment_name="PFBM-MCP-ENV",
            solution_stack_name="64bit Amazon Linux 2023 v4.5.1 running Docker",
            option_settings=option_settings,
            version_label=app_version.ref
        )
        
        # Output the URL
        CfnOutput(
            self, "PFBM-MCP-URL",
            description="URL of PFBM MCP Service",
            value=f"http://{environment.attr_endpoint_url}"
        )

app = App()

MCPServerStack(
    app, 
    config.get('deployment', {}).get('NAME', 'PFBM-MCP-SERVER'),
)

app.synth()