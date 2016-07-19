#!/bin/bash

s3_key="$1"
s3_bucket="$2"
stack_name="$3"

exclude="-x *.pyc -x *test.py -x *.sh"
update_states="UPDATE_IN_PROGRESS UPDATE_COMPLETE_CLEANUP_IN_PROGRESS UPDATE_ROLLBACK_IN_PROGRESS UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS"

echo "$( date ) creating package"
[ -f ../${pkg_name} ] && rm ../${pkg_name}
output=$( zip -r ../${pkg_name} ./* ${exclude} 2>&1 )
if [ "${?}" -ne 0 ]; then
  echo "errors: ${output}"
  exit 1
fi

echo "$( date ) copying package to s3"
output=$( aws s3api put-object \
  --bucket ${s3_bucket} \
  --key ${s3_key} \
  --body ../${pkg_name} \
  --query 'VersionId' \
  --output text 2>&1 )
if [ "${?}" -ne 0 ]; then
  echo "errors: ${output}"
  exit 1
fi
version_id=${output}

echo "$( date ) updating cfn stack"
output=$( aws cloudformation update-stack \
  --stack-name ${stack_name} \
  --template-body file://./template.json \
  --capabilities CAPABILITY_IAM \
  --parameters ParameterKey=S3Version,ParameterValue=${version_id} 2>&1 )
if [ "${?}" -ne 0 ]; then
  echo "errors: ${output}"
  exit 1
fi

echo "$( date ) waiting for cfn update"
while [ 1 ]; do
  output=$( aws cloudformation list-stacks \
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
      --stack-status-filter ${update_states}  \
      --query 'StackSummaries[?StackName==`'${stack_name}'`].StackName' \
      --output text 2>&1 )
    break
  fi
done

echo "$( date ) update complete ( ${stack_state} )"
