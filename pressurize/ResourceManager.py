import json
from collections import OrderedDict

from redleader.cluster import Cluster, AWSContext
import redleader.resources as r
import random
import pressurize.AWSManager

from redleader.resources.elasticbeanstalk import *
from redleader.managers import ElasticBeanstalkManager

from redleader.util import sanitize

class ResourceManager(object):
    """
    ResourceManager coordinates AWS resources for
    a pressurize deployment
    """
    def __init__(self, controller):
        self._controller = controller

    def _cluster_name(self):
        return self._controller.deployment_name + "Cluster"

    def prefix_name(self, name):
        return self._controller.deployment_name + name

    def default_dynamo_tables(self, context):
        """
        Create default DynamoDB tables
        """
        model_instance_state_config = {
            "key_schema": OrderedDict([
                ('model_name', 'HASH'),
                ('server_address', 'RANGE'),
            ]),
            "attribute_definitions": {
                'model_name': 'S',
                'server_address': 'S',
            }
        }
        model_instance_state_table = r.DynamoDBTableResource(
            context, self.prefix_name("model_instance_state"),
            attribute_definitions=model_instance_state_config['attribute_definitions'],
            key_schema=model_instance_state_config['key_schema'],
            write_units=5, read_units=5
        )
        return [model_instance_state_table]

    def bucket_resources(self, context, config):
        """
        Create RedLeader bucket resources for any referenced buckets,
        so that our deployed elastic beanstalk applications can be granted
        appropriate IAM permissions
        """
        bucket_names = {}
        for model in config["models"]:
            for resource in model["required_resources"]:
                if("s3://" in resource):
                    parts = resource.split("/")
                    if len(parts < 3):
                        raise RuntimeError("Invalid s3 url in configuration: %s" % resource)
                    bucket_names[parts[2]] = True

        bucket_resources = []
        for bucket_name in bucket_names:
            bucket_resources.append(r.S3BucketResource(context, bucket_name))

        return bucket_resources

    def elastic_beanstalk_bucket(self, name):
        return "pressurizebucket" + sanitize(name)

    def cname_prefix(self, name):
        return "pressurize-" + sanitize(name)

    def elastic_beanstalk_resources(self, name, version, source_file, config_options):
        """
        manager = ElasticBeanstalkManager(self.context)
        self.upload_app(manager, bucket_name)
        """

        app = ElasticBeanstalkAppResource(self.context, sanitize(name))
        cname_prefix = self.cname_prefix(name)
        version = ElasticBeanstalkAppVersionResource(
            self.context,
            app,
            self.elastic_beanstalk_bucket(name),
            source_file.split("/")[-1],
            version)

        config = ElasticBeanstalkConfigTemplateResource(
            self.context,
            app,
            config_options,
            solution_stacks["docker"],
            "Pressurize docker elastic beanstalk config %s" % name)

        env = ElasticBeanstalkEnvResource(
            self.context,
            app,
            version,
            config,
            cname_prefix,
            "Pressurize env %s" % n
        )
        return [app, version, config, env]

    def create_model_cluster(self, source_file, model_name, min_size=1, max_size=2):
        context = AWSContext()
        cluster = Cluster(self._cluster_name() + model_name, context)
        resources = self.elastic_beanstalk_resources()
        version = str(random.randint(0, 100000))

        config_options = {
            "aws:autoscaling:asg": {
                "MinSize": "1",
                "MaxSize": "2"
            },
            "aws:elasticbeanstalk:environment": {
                "EnvironmentType": "LoadBalanced"
            }
        }

        resources = elastic_beanstalk_resources(model_name,
                                    version,
                                    source_file,
                                    config_options)
        for resource in resources:
            cluster.add_resource(resource)

        return cluster

    def create_general_cluster(self):
        """
        Create a RedLeader cluster for AWS resource creation
        """
        context = AWSContext()
        cluster = Cluster(self._cluster_name(), context)

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
