#!/bin/bash

cfn_template="$1"
region="$2"
src_pkg="$3"
s3_key="$4"
s3_bucket="$5"
stack_name="$6"

exclude="-x *.pyc -x *test.py -x *.sh"
update_states="UPDATE_IN_PROGRESS UPDATE_COMPLETE_CLEANUP_IN_PROGRESS UPDATE_ROLLBACK_IN_PROGRESS UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS"

echo "$( date ) creating package"
[ -f ${src_pkg} ] && rm ${src_pkg}
[ -f $( dirname ${src_pkg} ) ] || mkdir $( dirname ${src_pkg} )
output=$( zip -r ${src_pkg} ./* ${exclude} 2>&1 )
if [ "${?}" -ne 0 ]; then
  echo "errors: ${output}"
  exit 1
fi

echo "$( date ) copying package to s3"
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
version_id=${output}

echo "$( date ) updating cfn stack"
output=$( aws cloudformation update-stack \
  --region ${region} \
  --stack-name ${stack_name} \
  --template-body file://${cfn_template} \
  --capabilities CAPABILITY_IAM \
  --parameters ParameterKey=S3Bucket,ParameterValue=${bucket_name} \
               ParameterKey=S3Key,ParameterValue=${funct_name}/${funct_name}-pkg.zip \
               ParameterKey=S3Version,ParameterValue=${version_id} \
               ParameterKey=ExecRole,ParameterValue=${lambda_exec_role} 2>&1 )
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
