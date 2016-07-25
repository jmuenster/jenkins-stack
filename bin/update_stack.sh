#!/bin/bash

region="$1"
program="$2"
domain="$3"
stage="$4"
version="$5"
repo_dir="$6"
s3_bucket="$7"
stack_name="$8"

exclude="-x *.pyc -x *test.py -x *.sh"
update_states="UPDATE_IN_PROGRESS UPDATE_COMPLETE_CLEANUP_IN_PROGRESS UPDATE_ROLLBACK_IN_PROGRESS UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS"

# todo: validate that region/program/domain/stage/version are validvia regex
# todo: validate that repo_dir exists, cfn template exists, src dir exists
# todo: validate cfn template is valid json
# todo: validate cfn template is a valid cfn template
# todo: validate that s3 bucket exists and is writable
# todo: validate that stack_name exists

for function in $( ls ${repo_dir}/src ); do

  echo "$( date ) creating packages for ${function}"

  src_pkg="${repo_dir}/tmp/${function}/lambda_function.zip"
  [ -f ${src_pkg} ] && rm ${src_pkg}
  [ -f $( dirname ${src_pkg} ) ] || mkdir -p $( dirname ${src_pkg} )
  output=$( cd ${repo_dir}/src/${function} && zip -r ${src_pkg} ./* ${exclude} 2>&1 )
  if [ "${?}" -ne 0 ]; then
    echo "errors: ${output}"
    exit 1
  fi

  echo "$( date ) copying package to s3"

  # todo: get the ${stack_name}'s physical id for ${function} using ${function}'s logical name
  # todo: get ${function}'s sha256 sum, compare with sha256 sum of ${src_pkg}
  # todo: ${function}'s and ${src_pkg}'s sha256 sum's match, fetch the current s3 object version for ${function}
  # todo: else the following s3api put-object

  s3_key=${function}/${function}-pkg.zip
  output=$( aws s3api put-object \
    --region ${region} \
    --bucket ${s3_bucket} \
    --key ${s3_key} \
    --body ${src_pkg} \
    --query 'VersionId' \
    --output text 2>&1 )
  if [ "${?}" -ne 0 ]; then
    echo "errors: ${output}"
    exit 1
  fi
  s3_obj_version=${output}
  echo "version: ${s3_obj_version}"

done

echo "$( date ) updating cfn stack"

output=$( aws cloudformation update-stack \
  --region ${region} \
  --stack-name ${stack_name} \
  --template-body file://${repo_dir}/cfn/template.json \
  --capabilities CAPABILITY_IAM \
  --parameters ParameterKey=Program,ParameterValue=${program} \
               ParameterKey=Domain,ParameterValue=${domain} \
               ParameterKey=Stage,ParameterValue=${stage} \
               ParameterKey=Version,ParameterValue=${version} \
               ParameterKey=S3Bucket,ParameterValue=${s3_bucket} \
               ParameterKey=S3Key,ParameterValue=${s3_key} \
               ParameterKey=S3Version,ParameterValue=${s3_obj_version} 2>&1 )
if [ "${?}" -ne 0 ]; then
  echo "errors: ${output}"
  exit 1
fi

echo "$( date ) waiting for cfn update"

while [ 1 ]; do
  output=$( aws cloudformation list-stacks \
    --region ${region} \
    --stack-status-filter ${update_states}  \
    --query 'StackSummaries[?StackName==`'${stack_name}'`].StackName' \
    --output text 2>&1 )
  if [ "${?}" -ne 0 ]; then
    echo "errors: ${output}"
    exit 1
  elif [ "${output}" == "${stack_name}" ]; then
    sleep 5
  else
    stack_state= $( aws cloudformation list-stacks \
      --region ${region} \
      --stack-status-filter ${update_states}  \
      --query 'StackSummaries[?StackName==`'${stack_name}'`].StackName' \
      --output text 2>&1 )
    break
  fi
done

echo "$( date ) update complete ( ${stack_state} )"
