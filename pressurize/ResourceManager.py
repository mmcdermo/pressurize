import json
import csv
import random
from collections import OrderedDict

from redleader.cluster import Cluster, AWSContext
from redleader.resources.elasticbeanstalk import *
from redleader.managers import ElasticBeanstalkManager
from redleader.util import sanitize
import redleader.resources as r

import pressurize.AWSManager

class ResourceManager(object):
    """
    ResourceManager coordinates AWS resources for
    a pressurize deployment
    """
    def __init__(self, controller):
        self._controller = controller

        # Our AWSManager
        self._aws_manager = self._controller._aws_manager

        # RedLeader AWSContext
        self._aws_context = AWSContext(
            aws_profile = self._controller._aws_profile,
            aws_region=self._controller.config['aws_region'])

    def _cluster_name(self):
        return self._controller.config["deployment_name"] + "Cluster"

    def prefix_name(self, name):
        return self._controller.config["deployment_name"] + name

    def default_dynamo_tables(self, context):
        """
        Create default DynamoDB tables
        """
        cache_config = {
            "key_schema": OrderedDict([
                ('key', 'HASH'),
            ]),
            "attribute_definitions": {
                'key': 'S'
            }
        }
        self.cache_table = r.DynamoDBTableResource(
            context, self.prefix_name("cache"),
            attribute_definitions=cache_config['attribute_definitions'],
            key_schema=cache_config['key_schema'],
            write_units=5, read_units=5
        )
        print("DynamoDB cache table name", self.prefix_name("cache"))

        auth_config = {
            "key_schema": OrderedDict([
                ('token_key', 'HASH'),
            ]),
            "attribute_definitions": {
                'token_key': 'S'
            }
        }
        self.auth_table = r.DynamoDBTableResource(
            context, self.prefix_name("auth"),
            attribute_definitions=auth_config['attribute_definitions'],
            key_schema=auth_config['key_schema'],
            write_units=5, read_units=5
        )
        print("DynamoDB auth table name", self.prefix_name("cache"))

        return [self.cache_table, self.auth_table]

    def bucket_resources(self, context, model):
        """
        Create RedLeader bucket resources for any referenced buckets,
        so that our deployed elastic beanstalk applications can be granted
        appropriate IAM permissions
        """
        bucket_names = {}
        dynamodb_table_names = {}
        cloudsearch_configs = []
        for resource_name in model["required_resources"]:
            resource = model["required_resources"][resource_name]
            if("s3://" in resource):
                parts = resource.split("/")
                if len(parts) < 3:
                    raise RuntimeError("Invalid s3 url in configuration: %s" % resource)
                bucket_names[parts[2]] = True
            if("dynamodb://" in resource):
                parts = resource.split("//")
                if len(parts) < 2:
                    raise RuntimeError("Invalid dynamodb table in configuration: %s" % resource)
                dynamodb_table_names[parts[2]] = { "aws_region":
                                                   context._aws_region if len(parts) < 3 else parts[1] }
            if("cloudsearch://" in resource):
                cloudsearch_configs = cloudsearch_configs.append(
                    model["required_resources"][resource_name]
                )

        bucket_resources = []
        for bucket_name in bucket_names:
            bucket_resources.append(r.S3BucketResource(context, bucket_name))

        table_resources = []
        for table_name in dynamodb_table_names:
            conf = dynamodb_table_names[table_name]
            print("Creating resource ", table_name, conf['aws_region'])
            bucket_resources.append(r.DynamoDBTableResource(context, table_name, aws_region=conf['aws_region']))

        cloudsearch_resources = []
        for item in cloudsearch_configs:
            cloudsearch_resources.append(CloudSearch(
                domain_name=item['domain_name']
            ))

        return bucket_resources + table_resources + cloudsearch_configs

    def elastic_beanstalk_bucket(self):
        return "pressurizebucket" + sanitize(self._controller.config['deployment_name'])

    def cname_prefix(self, name):
        return sanitize(self._controller.config["deployment_name"]) + "-" + sanitize(name)

    def elastic_beanstalk_api_resources(self, version, source_file, config_options):
        """
        Create RedLeader resources for the API elastic beanstalk deployment
        """
        context = self._aws_context
        app = ElasticBeanstalkAppResource(context, self.prefix_name("api"))
        cname_prefix = self.cname_prefix("api")
        table_resources = self.default_dynamo_tables(context)
        permission_resources = list(map(lambda x: r.ReadWritePermission(x), table_resources))
        version = ElasticBeanstalkAppVersionResource(
            context,
            app,
            self.elastic_beanstalk_bucket(),
            source_file.split("/")[-1],
            version)
        config = ElasticBeanstalkConfigTemplateResource(
            context,
            app,
            config_options,
            solution_stacks["docker"],
            "Pressurize API beanstalk config",
            permission_resources=permission_resources
        )
        env = ElasticBeanstalkEnvResource(
            context,
            app,
            version,
            config,
            cname_prefix,
            "Pressurize API env"
        )
        return [app, version, config, env] + table_resources

    def elastic_beanstalk_model_resources(self, name, version, source_file, config_options):
        """
        Create RedLeader resources for a single elastic beanstalk model deployment
        """
        context = self._aws_context
        app = ElasticBeanstalkAppResource(context, self.prefix_name(sanitize(name)))
        cname_prefix = self.cname_prefix(name)
        model_config = self._controller.models[name]
        bucket_resources = self.bucket_resources(context, model_config)

        permission_resources = list(map(lambda x: r.ReadWritePermission(x), bucket_resources))
        version = ElasticBeanstalkAppVersionResource(
            context,
            app,
            self.elastic_beanstalk_bucket(),
            source_file.split("/")[-1],
            version)
        config = ElasticBeanstalkConfigTemplateResource(
            context,
            app,
            config_options,
            solution_stacks["docker"],
            "Pressurize docker elastic beanstalk config %s" % name,
            permission_resources=permission_resources
        )
        env = ElasticBeanstalkEnvResource(
            context,
            app,
            version,
            config,
            cname_prefix,
            "Pressurize env %s" % name
        )
        return [app, version, config, env] + bucket_resources

    def create_api_cluster(self, source_file, min_size=1, max_size=2):
        """
        Create a pressurize API cluster based on the Controller's config.

        InstanceType for this elasticbeanstalk deployment is determined by
        1) `instance_type` property
        2)  Defaults to t2.micro
        """

        cluster = Cluster(sanitize(self._cluster_name() + "api"), self._aws_context)
        version = str(random.randint(0, 100000))

        conf = self._controller.config
        config_options = {
            "aws:autoscaling:asg": {
                "MinSize": str(conf.get('api_min_size', min_size)),
                "MaxSize": str(conf.get('api_max_size', max_size))
            },
            "aws:autoscaling:launchconfiguration": {
                "InstanceType": conf.get('api_instance_type', 't2.micro')
            },
            "aws:elasticbeanstalk:command": {
                "DeploymentPolicy": "Immutable"
            },
            "aws:autoscaling:updatepolicy:rollingupdate": {
                "RollingUpdateType": "Immutable"
            },
            "aws:elasticbeanstalk:healthreporting:system": {
                "SystemType": "enhanced"
            },
            "aws:elasticbeanstalk:environment": {
                "EnvironmentType": "LoadBalanced"
            },
            "aws:elasticbeanstalk:cloudwatch:logs": {
                "StreamLogs": True,
                "DeleteOnTerminate": False,
                "RetentionInDays": 30
            }
        }
        resources = self.elastic_beanstalk_api_resources(version,
                                                         source_file,
                                                         config_options)
        for resource in resources:
            cluster.add_resource(resource)
        return cluster

    def read_instance_types(self, instance_types_file="instance_types.csv"):
        instance_types = []
        with open(instance_types_file, 'r') as f:
            x = csv.DictReader(f)
            for row in x:
                instance_types.append({
                    "name": row["Name"],
                    "memory": float(row["Memory"]),
                    "ecu": float(row["ECU"] if row["ECU"] != "Variable" else "0.5"),
                    "cost": float(row["Hourly Cost"][1:])
                })
        return instance_types

    def determine_instance_type(self, required_ecu, required_memory):
        """
        Find the least expensive EC2 instance that meets the provided
        ECU and memory requirements
        """
        if not hasattr(self, 'instance_types'):
            path = "/" + os.path.join(*(__file__.split("/")[:-1] + ["instance_types.csv"]))
            self.instance_types = self.read_instance_types(path)

        candidates = []
        for instance_idx in range(len(self.instance_types)):
            instance = self.instance_types[instance_idx]
            if instance['memory'] > required_memory and instance['ecu'] > required_ecu:
                candidates.append(instance)
        lwm = candidates[0]['cost']
        least_expensive = candidates[0]
        for candidate in candidates:
            if candidate['cost'] < lwm:
                least_expensive = candidate
                lwm = candidate['cost']
        return least_expensive

    def create_model_cluster(self, source_file, model_name, min_size=1, max_size=2):
        """
        Create a pressurize model cluster based on the Controller's config.

        InstanceType for this elasticbeanstalk deployment is determined by
         1) `required_ecu` and `required_memory` parameters.
         2) `instance_type` property
         3)  Defaults to t2.micro
        """

        cluster = Cluster(sanitize(self._cluster_name() + model_name), self._aws_context)
        version = str(random.randint(0, 100000))

        model_config = self._controller.models[model_name]

        # Determine instance type
        instance_type = 't2.micro'
        if 'required_ecu' in model_config:
            instance_type = self.determine_instance_type(
                model_config['required_ecu'],
                model_config['required_memory'])['name']
            print("Determined instance type: ", instance_type)
        if 'instance_type' in model_config:
            instance_type = model_config['instance_type']

        config_options = {
            "aws:autoscaling:asg": {
                "MinSize": str(model_config.get('min_size', min_size)),
                "MaxSize": str(model_config.get('max_size', max_size))
            },
            "aws:autoscaling:launchconfiguration": {
                "InstanceType": instance_type,
                "RootVolumeSize": str(model_config.get('storage_gb', 16))
            },
            "aws:elasticbeanstalk:command": {
                "DeploymentPolicy": "Immutable"
            },
            "aws:autoscaling:updatepolicy:rollingupdate": {
                "RollingUpdateType": "Immutable"
            },
            "aws:elasticbeanstalk:healthreporting:system": {
                "SystemType": "enhanced"
            },
            "aws:elasticbeanstalk:environment": {
                "EnvironmentType": "LoadBalanced"
            },
            "aws:elasticbeanstalk:cloudwatch:logs": {
                "StreamLogs": True,
                "DeleteOnTerminate": False,
                "RetentionInDays": 30
            }
        }
        resources = self.elastic_beanstalk_model_resources(model_name,
                                                           version,
                                                           source_file,
                                                           config_options)

        for resource in resources:
            cluster.add_resource(resource)
        return cluster

    def create_general_cluster(self):
        """
        Create a RedLeader cluster for AWS resource creation

        Not currently used.
        """
        cluster = Cluster(self._cluster_name(), self._aws_context)

        # Create a ref to cloudwatch logs so we can create an appropriate role
        logs = r.CloudWatchLogs(context)
        cluster.add_resource(logs)

        # Incorporate resources needed by individual models and our tables
        resources = self.create_bucket_resources() + \
                    self.default_dynamo_tables(context) + \
                    self.elastic_beanstalk_resources()
        for resource in resources:
            cluster.add_resource(resource)

        # Create our configuration bucket
        config_bucket = r.S3BucketResource(self.prefix_name("config"))
        cluster.add_resource(config_bucket)

        # Create a role for ELBS
        permissions = []
        for resource in resources:
            permissions.append(r.ReadWritePermission(resource))
        permissions.append(r.ReadWritePermission(logs))
        self.beanstalk_role = r.IAMRoleResource(context,
                                                permissions=permissions,
                                                services=["elasticbeanstalk.amazonaws.com"])
        cluster.add_resource(self.beanstalk_role)
        print(json.dumps(cluster.cloud_formation_template(), indent=4))
        return cluster
