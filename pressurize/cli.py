import os
import json
import os.path
import click
import pressurize
from pressurize import Controller

import botocore

@click.group()
@click.version_option(version=pressurize.__version__, message='%(prog)s %(version)s')
@click.option('--debug/--no-debug', default=False,
              help='Write debug logs to standard error.')
@click.pass_context
def cli(ctx, debug=False):
    if not ctx.obj:
        ctx.obj = {}
    ctx.obj['config_file'] = 'pressurize.json'
    ctx.obj['project_dir'] = os.getcwd()
    ctx.obj['debug'] = debug

@cli.command()
@click.option('--aws-profile', default=None,
              help='AWS Profile to use for cluster commands')
@click.pass_context
def deploy(ctx, aws_profile):
    if ctx.obj['config_file'] not in os.listdir(ctx.obj['project_dir']):
        click.echo('No pressurize.json file found in directory')
        raise click.Abort()

    print("Config path", os.path.join(ctx.obj['project_dir'], ctx.obj['config_file']))
    with open(os.path.join(ctx.obj['project_dir'], ctx.obj['config_file']), 'r') as f:
        config = json.load(f)
    try:
        controller = Controller.Controller(config, aws_profile=aws_profile)
    except Exception as e:
       click.echo('Error with config: %s' % e)
       raise click.Abort()

    # Deploy API
    try:
        controller.deploy_api()
    except botocore.exceptions.ClientError as e:
        print("Failed to deploy API. %s" % e)

    # Deploy Models
    try:
        controller.deploy_models()
    except botocore.exceptions.ClientError as e:
        print("Failed to deploy models. %s" % e)


@cli.command(name="deploy-model")
@click.argument("model_name")
@click.option('--aws-profile', default=None,
              help='AWS Profile to use for cluster commands')
@click.pass_context
def deploy_model(ctx, model_name, aws_profile):
    if ctx.obj['config_file'] not in os.listdir(ctx.obj['project_dir']):
        click.echo('No pressurize.json file found in directory')
        raise click.Abort()

    print("Config path", os.path.join(ctx.obj['project_dir'], ctx.obj['config_file']))
    with open(os.path.join(ctx.obj['project_dir'], ctx.obj['config_file']), 'r') as f:
        config = json.load(f)
    try:
        controller = Controller.Controller(config, aws_profile=aws_profile)
    except Exception as e:
       click.echo("Error with config: %s" % e)
       raise click.Abort()

    if model_name not in controller.models:
        click.echo("Model %s not found in config")
        raise click.Abort()

    # Deploy Model
    source_path = os.getcwd()
    try:
        controller.deploy_model(source_path, model_name)
    except botocore.exceptions.ClientError as e:
        print("Failed to deploy model %s. %s" % (model_name, e))

@cli.command(name="deploy-models")
@click.option('--aws-profile', default=None,
              help='AWS Profile to use for cluster commands')
@click.pass_context
def deploy_models(ctx, aws_profile):
    if ctx.obj['config_file'] not in os.listdir(ctx.obj['project_dir']):
        click.echo('No pressurize.json file found in directory')
        raise click.Abort()

    print("Config path", os.path.join(ctx.obj['project_dir'], ctx.obj['config_file']))
    with open(os.path.join(ctx.obj['project_dir'], ctx.obj['config_file']), 'r') as f:
        config = json.load(f)
    try:
        controller = Controller.Controller(config, aws_profile=aws_profile)
    except Exception as e:
       click.echo("Error with config: %s" % e)
       raise click.Abort()

    # Deploy Models
    try:
        controller.deploy_models()
        print("------------------------")
        print("Models are being updated.")
    except botocore.exceptions.ClientError as e:
        print("Failed to deploy models. %s" % e)

@cli.command(name="deploy-api")
@click.option('--aws-profile', default=None,
              help='AWS Profile to use for cluster commands')
@click.pass_context
def deploy_api(ctx, aws_profile):
    if ctx.obj['config_file'] not in os.listdir(ctx.obj['project_dir']):
        click.echo('No pressurize.json file found in directory')
        raise click.Abort()

    print("Config path", os.path.join(ctx.obj['project_dir'], ctx.obj['config_file']))
    with open(os.path.join(ctx.obj['project_dir'], ctx.obj['config_file']), 'r') as f:
        config = json.load(f)
    try:
        controller = Controller.Controller(config, aws_profile=aws_profile)
    except Exception as e:
       click.echo("Error with config: %s" % e)
       raise click.Abort()

    # Deploy Models
    try:
        controller.deploy_api()
    except botocore.exceptions.ClientError as e:
        print("Failed to deploy API. %s" % e)

@cli.command()
@click.pass_context
@click.argument("model_name")
@click.option("--port", default=5001)
@click.option("--docker/--no-docker", default=True)
@click.option('--aws-profile', default=None,
              help='AWS Profile to use for cluster commands')
def local(ctx, model_name, port, docker, aws_profile):
    if ctx.obj['config_file'] not in os.listdir(ctx.obj['project_dir']):
        click.echo('No pressurize.json file found in directory')
        raise click.Abort()

    print("Config path", os.path.join(ctx.obj['project_dir'], ctx.obj['config_file']))
    with open(os.path.join(ctx.obj['project_dir'], ctx.obj['config_file']), 'r') as f:
        config = json.load(f)
    try:
        controller = Controller.Controller(config, aws_profile=aws_profile)
    except Exception as e:
        click.echo('Error with config: %s' % e)
        raise click.Abort()
    controller.run_local(model_name, port=port, docker=docker)

@cli.command(name="dry-run")
@click.option('--aws-profile', default=None,
              help='AWS Profile to use for cluster commands')
@click.pass_context
def dry_run(ctx, aws_profile):
    if ctx.obj['config_file'] not in os.listdir(ctx.obj['project_dir']):
        click.echo('No pressurize.json file found in directory')
        raise click.Abort()

    print("Config path", os.path.join(ctx.obj['project_dir'], ctx.obj['config_file']))
    with open(os.path.join(ctx.obj['project_dir'], ctx.obj['config_file']), 'r') as f:
        config = json.load(f)
    try:
        controller = Controller.Controller(config, aws_profile=aws_profile)
    except Exception as e:
        click.echo('Error with config: %s' % e)
        raise click.Abort()
    print(json.dumps(controller.deploy_api(dry_run=True), indent=4))
    print(json.dumps(controller.deploy_models(dry_run=True), indent=4))

@cli.command(name="create-token")
@click.option('--aws-profile', default=None,
              help='AWS Profile to use for cluster commands')
@click.option("--token-lifetime-in-hours", default=24*30*12)
@click.pass_context
def create_token(ctx, aws_profile, token_lifetime_in_hours):
    if ctx.obj['config_file'] not in os.listdir(ctx.obj['project_dir']):
        click.echo('No pressurize.json file found in directory')
        raise click.Abort()

    print("Config path", os.path.join(ctx.obj['project_dir'], ctx.obj['config_file']))
    with open(os.path.join(ctx.obj['project_dir'], ctx.obj['config_file']), 'r') as f:
        config = json.load(f)
    try:
        controller = Controller.Controller(config, aws_profile=aws_profile)
    except Exception as e:
        click.echo('Error with config: %s' % e)
        raise click.Abort()

    token = controller.create_token(token_lifetime_in_hours)
    print("----- Generated Token ------")
    print(json.dumps(token, indent=4))


def main():
    cli(obj={})
