#!/root/.virtualenvs/saws/bin/python

import argparse
import boto3
import botocore
import hashlib
import logging
import os
import sys
import zipfile
 
logging.basicConfig( level=logging.INFO )

parser=argparse.ArgumentParser(description='This is a demo script by nixCraft.')

parser.add_argument('-r', '--Region', help='region to create the stack in', required=True )
parser.add_argument('-p', '--Program', help='program used for naming', required=True )
parser.add_argument('-d', '--Domain', help='domain used for naming', required=True )
parser.add_argument('-s', '--Stage', help='stage of deployment process this stack supports', required=True )
parser.add_argument('-v', '--Version', help='version of stack / services', required=True )
parser.add_argument('-c', '--Repo_dir', help='code repository containing cfn template, property files, etc', required=True )
parser.add_argument('-b', '--S3Bucket', help='s3 bucket used to deploy function code', required=True )
parser.add_argument('-n', '--StackName', help='name of stack being created / updated', required=True )

args=parser.parse_args()

stack_parameters=[]

logging.info( '-' * 20 )
for arg, value in sorted(vars(args).items()):
    logging.info( "{}: {}".format( arg, value ) )
    if arg not in [ 'StackName', 'Region', 'Repo_dir' ]:
        stack_parameters.append( { 'ParameterKey': arg, 'ParameterValue': value } )
logging.info( '-' * 20 )

cfn=boto3.client( 'cloudformation', region_name=args.Region )
lamb=boto3.client( 'lambda', region_name=args.Region )
s3=boto3.client( 's3', region_name=args.Region )

try:
    desc_stack_response=cfn.describe_stacks( StackName=args.StackName )
except botocore.exceptions.EndpointConnectionError as e:
    logging.error( 'region error:'.format ( e ) )
except botocore.exceptions.ClientError as e:
    if e.response['Error']['Code'] == 'ValidationError':
        logging.error( 'validation error: {}'.format( e.response['Error']['Message'] ) )
        sys.exit( 1 )
    else:
        logging.error( 'unexpected error: {}'.format( e.response['Error']['Message'] ) )
        sys.exit( 1 )

if not os.path.isdir( args.Repo_dir ):
    logging.error( "error: the repo directory ({}) doesn't exist".format( args.Repo_dir ) )
    sys.exit( 1 )

cfn_template=args.Repo_dir + '/cfn/template.json'

if not os.path.isfile( cfn_template ):
    logging.error( "error: the cfn template ({}) doesn't exist".format( cfn_template ) )
    sys.exit( 1 )

with open( cfn_template, 'r' ) as f:
    try:
        validate_response=cfn.validate_template( TemplateBody=f.read() )
    except botocore.exceptions.ClientError as e:
        logging.error( 'error while trying to validate the cfn template ({}): {}'.format( cfn_template, e.response['Error']['Message'] ) )
        sys.exit( 1 )

try:
    response=s3.list_objects( Bucket=args.S3Bucket )
except botocore.exceptions.ClientError as e:
    logging.error( 'error while trying to list_object in {}: {}'.format( args.S3Bucket, e.response['Error']['Message'] ) )
    sys.exit( 1 )

funct_names=next( os.walk( args.Repo_dir + '/src' ) )[1]

for funct_name in funct_names:

    src_dir=args.Repo_dir + '/src/' + funct_name
    pkg_dir=args.Repo_dir + '/tmp/' + funct_name
    pkg=pkg_dir + '/' + funct_name + '-pkg.zip'

    if not os.path.isdir( pkg_dir ):
        os.makedirs( pkg_dir )

    if os.path.isfile( pkg ):
        os.remove( pkg )

    zipf=zipfile.ZipFile( pkg, 'w', zipfile.ZIP_DEFLATED)
    for root, dirs, files in os.walk( src_dir ):
        for file in files:
            zipf.write( os.path.join( root, file ) )
    zipf.close()

    def hashfile(afile, hasher, blocksize=65536):
        buf=afile.read(blocksize)
        while len(buf) > 0:
            hasher.update(buf)
            buf=afile.read(blocksize)
        return hasher.hexdigest()

    funct_new_sha=[ ( fname, hashfile( open( fname, 'rb' ), hashlib.sha256() ) ) for fname in [ pkg ] ][0][1]

    try:
        stack_resource_response=cfn.describe_stack_resource( StackName=args.StackName, LogicalResourceId=funct_name )
    except botocore.exceptions.ClientError as e:
        logging.error( 'error while trying to describe the {} function resource: {}'.format( funct_name, e.response['Error']['Message'] ) )
        sys.exit( 1 )

    funct_phys_name=stack_resource_response[ 'StackResourceDetail' ][ 'PhysicalResourceId' ]

    try:
        describe_function_response=lamb.get_function( FunctionName=funct_phys_name )
    except botocore.exceptions.ClientError as e:
        logging.error( 'error while trying to describe the {} function: {}'.format( funct_name, e.response['Error']['Message'] ) )
        sys.exit( 1 )

    funct_current_sha=describe_function_response[ 'Configuration' ][ 'CodeSha256' ]

    print( funct_current_sha )

    try:
        pkg_writer=open( pkg, 'rb')
        pkg_dest=funct_name + '/' + funct_name + '-pkg.zip'
        put_object_response=s3.put_object( Bucket=args.S3Bucket, Key=pkg_dest, Body=pkg_writer ) 
        stack_parameters.append( { 'ParameterKey': funct_name + 'S3ObjectVersion', 'ParameterValue': put_object_response[ 'VersionId' ] } )
        stack_parameters.append( { 'ParameterKey': funct_name + 'S3Key', 'ParameterValue': pkg_dest } )
    except botocore.exceptions.ClientError as e:
        logging.error( 'error while trying to put the pkg in s3'.format( e.response['Error']['Message'] ) )
        sys.exit( 1 )



try:
    print( cfn_template )
    print( stack_parameters )
    with open( cfn_template, 'r' ) as f:
        response=cfn.update_stack( StackName=args.StackName, TemplateBody=f.read(), Parameters=stack_parameters, Capabilities=[ 'CAPABILITY_IAM' ] )
except botocore.exceptions.ClientError as e:
    logging.error( 'error while trying to update the {} stack: {}'.format( args.StackName, e.response['Error']['Message'] ) )
    sys.exit( 1 )

