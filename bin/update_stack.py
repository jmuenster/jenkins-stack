#!/root/.virtualenvs/saws/bin/python

import argparse
import boto3
import botocore
import hashlib
import logging
import pip
import os
import sys
import zipfile
 
action='update'
stack_info=''
stack_parameters=[]



# collect / log parameters

parser=argparse.ArgumentParser( )

parser.add_argument('-r', '--Region', help='region to create the stack in', required=True )
parser.add_argument('-p', '--Program', help='program used for naming', required=True )
parser.add_argument('-d', '--Domain', help='domain used for naming', required=True )
parser.add_argument('-s', '--Stage', help='stage of deployment process this stack supports', required=True )
parser.add_argument('-v', '--Version', help='version of stack / services', required=True )
parser.add_argument('-c', '--RepoDir', help='code repository containing cfn template, property files, etc', required=True )
parser.add_argument('-b', '--S3Bucket', help='s3 bucket used to deploy function code', required=True )
parser.add_argument('-n', '--StackName', help='name of stack being created / updated', required=True )
parser.add_argument('-e', '--VirtualEnvPkgDir', help='python virtualenv dir', required=True )

args=parser.parse_args()

logging.basicConfig( level=logging.WARN )

logging.info( '-' * 20 )
for arg, value in sorted(vars(args).items()):
    logging.info( "{}: {}".format( arg, value ) )
    if arg not in [ 'StackName', 'Region', 'RepoDir' ]:
        stack_parameters.append( { 'ParameterKey': arg, 'ParameterValue': value } )
logging.info( '-' * 20 )



# create clients

cfn=boto3.client( 'cloudformation', region_name=args.Region )
lamb=boto3.client( 'lambda', region_name=args.Region )
s3=boto3.client( 's3', region_name=args.Region )



# functions

def get_files( dir ):

    file_set=[]
    for dir_, _, files in os.walk( dir ):
        for file in files:
            rel_dir = os.path.relpath( dir_, dir )
            rel_file = os.path.join( rel_dir, file )
            file_set.append( rel_file )
    return file_set

def get_functions( repo_dir ):

    return next( os.walk( repo_dir + '/src' ) )[ 1 ]

def add_files_to_archive( archive, dirs ):

    zipf = zipfile.ZipFile( archive, 'w', zipfile.ZIP_DEFLATED)
    for dir in dirs:
        file_set = get_files( dir )
        for file in file_set:
            zipf.write( os.path.join( dir, file ), file )
    zipf.close()

def get_stack_info ( stack_name ):

    global action
    global stack_info
    try:
        stack_info = cfn.describe_stacks( StackName = stack_name )
    except botocore.exceptions.EndpointConnectionError as e:
        logging.error( 'region error:'.format ( e ) )
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Message'] == 'Stack with id {} does not exist'.format( stack_name ):
            logging.info( 'stack {} does not exist, creating'.format( stack_name ) )
            action='create'
        elif e.response['Error']['Code'] == 'ValidationError':
            logging.error( 'validation error: {}'.format( e.response['Error']['Message'] ) )
            sys.exit( 1 )
        else:
            logging.error( 'unexpected error: {}'.format( e.response['Error']['Message'] ) )
            sys.exit( 1 )

def hashfile(afile, hasher, blocksize = 65536):
    buf = afile.read(blocksize)
    while len(buf) > 0:
        hasher.update(buf)
        buf = afile.read(blocksize)
    return hasher.hexdigest()

def put_package_to_s3 ( package_name, function_name, bucket_name ):

    global stack_parameters
    try:
        package_writer = open( package_name, 'rb')
        package_dest = function_name + '/' + function_name + '-pkg.zip'
        put_object_response = s3.put_object( Bucket = bucket_name, Key = package_dest, Body = package_writer ) 
        stack_parameters.append( { 'ParameterKey': function_name + 'S3ObjectVersion', 'ParameterValue': put_object_response[ 'VersionId' ] } )
        stack_parameters.append( { 'ParameterKey': function_name + 'S3Key', 'ParameterValue': package_dest } )
    except botocore.exceptions.ClientError as e:
        logging.error( 'error while trying to put the pkg in s3'.format( e.response['Error']['Message'] ) )
        sys.exit( 1 )

def package_function( repo_dir, function_name, virtualenv_dir ):

    function_src_dir = repo_dir + '/src/' + function_name
    package_dir = repo_dir + '/tmp/' + function_name
    package = package_dir + '/' + function_name + '-pkg.zip'

    if not os.path.isdir( package_dir ):
        os.makedirs( package_dir )

    if os.path.isfile( package ):
        os.remove( package )

    with open( function_src_dir + '/packages.txt', 'r' ) as file:
        for package_name in file:
            pip.main( [ 'install', package_name ] )

    add_files_to_archive( package, [ function_src_dir, virtualenv_dir ] )

    package_sha = [ ( fname, hashfile( open( fname, 'rb' ), hashlib.sha256() ) ) for fname in [ package ] ][0][1]

    return { "package_name": package, "package_sha": package_sha }

def get_function_sha ( stack_name, function_name ):

    try:
        response = cfn.describe_stack_resource( StackName = stack_name, LogicalResourceId = function_name )
        function_phys_name = response[ 'StackResourceDetail' ][ 'PhysicalResourceId' ]
        describe_function_response = lamb.get_function( FunctionName = function_phys_name )
        return describe_function_response[ 'Configuration' ][ 'CodeSha256' ]
    except botocore.exceptions.ClientError as e:
        logging.error( 'error while trying to describe the {} function resource: {}'.format( function_name, e.response['Error']['Message'] ) )
        sys.exit( 1 )

def create_stack ( stack_name, template, parameters ):

    try:
        with open( template, 'r' ) as f:
            response=cfn.create_stack( StackName=stack_name, TemplateBody=f.read(), Parameters=parameters, Capabilities=[ 'CAPABILITY_IAM' ] )
        cfn_waiter = cfn.get_waiter( 'stack_create_complete' )
        cfn_waiter.wait( StackName = stack_name )
    except botocore.exceptions.ClientError as e:
        logging.error( 'error while trying to create the {} stack: {}'.format( stack_name, e.response['Error']['Message'] ) )
        sys.exit( 1 )

def update_stack ( stack_name, template, parameters ):

    try:
        with open( template, 'r' ) as f:
            response=cfn.update_stack( StackName=stack_name, TemplateBody=f.read(), Parameters=parameters, Capabilities=[ 'CAPABILITY_IAM' ] )
        cfn_waiter = cfn.get_waiter( 'stack_update_complete' )
        cfn_waiter.wait( StackName = stack_name )
    except botocore.exceptions.ClientError as e:
        logging.error( 'error while trying to update the {} stack: {}'.format( stack_name, e.response['Error']['Message'] ) )
        sys.exit( 1 )

def main ():

    stack_info = get_stack_info( args.StackName )

    if not os.path.isdir( args.RepoDir ):
        logging.error( "error: the repo directory ({}) doesn't exist".format( args.RepoDir ) )
        sys.exit( 1 )

    cfn_template=args.RepoDir + '/cfn/template.json'

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

    for function_name in get_functions( args.RepoDir ):
        logging.info( 'packaging {}'.format( function_name ) )
        response = package_function( args.RepoDir, function_name, args.VirtualEnvPkgDir )
        put_package_to_s3( response[ 'package_name' ], function_name, args.S3Bucket )
        package_sha = response[ 'package_sha' ]
        if action == 'update':
            function_sha=get_function_sha( args.StackName, function_name )

    if action == 'create':
        logging.info( 'creating {}'.format( args.StackName ) )
        create_stack( args.StackName, cfn_template, stack_parameters )
    elif action == 'update':
        logging.info( 'updating {}'.format( args.StackName ) )
        update_stack( args.StackName, cfn_template, stack_parameters )



main( )


