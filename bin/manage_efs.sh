#!/bin/bash

fs_log_id='Efs'
mount_dir='/efs'

bail() { echo -e "errors while: ${1}\n${2}"; exit 1; }



verb="fetching az, inst id and region from instance metadata" && echo "${verb}"

az=$( curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone 2>&1 ) || bail "${verb}" "${az}"
inst_id=$( curl -s http://169.254.169.254/latest/meta-data/instance-id 2>&1 ) || bail "${verb}" "${inst_id}"
#region=$( curl -s http://169.254.169.254/latest/dynamic/instance-identity/document |sed -n 's/\ *"region" : "\(.*\)"/\1/p' 2>&1 ) || bail "${verb}" "${region}"
region=$( echo "${az:0:-1}" 2>&1 ) || bail "${verb}" "${region}"

echo "az: ${az}, inst_id: ${inst_id}, region: ${region}"


verb="fetching stack name from ec2 api" && echo "${verb}"

stack_name=$( aws ec2 describe-tags --region ${region} --filters "Name=resource-id,Values=${inst_id}" --query 'Tags[?Key==`aws:cloudformation:stack-name`].Value' --output text 2>&1 ) || \
  bail "${verb}" "${stack_name}"

if [ $? -ne 0 ]; then

  echo "problems while trying to find stack:"
  echo "${stack_name}"
  exit 1

elif [ "${stack_name}" == "" ]; then

  echo "not able to retrieve stack name, exiting"
  exit 0

fi



verb="fetching filesystem id from cloudformation api" && echo "${verb}"

fs_id=$( aws cloudformation describe-stack-resource --region ${region} --stack-name ${stack_name} --logical-resource-id ${fs_log_id} --query 'StackResourceDetail.PhysicalResourceId' --output text 2>&1 ) || bail "${verb}" "${fs_id}"

if [ $? -ne 0 ]; then

  echo "problems while trying to find the fs id:"
  echo "${fs_id}"
  exit 1

elif [ "${fs_id}" == "" ]; then

  echo "not able to retrieve the fs id, exiting"
  exit 0

fi



verb="creating filesystem mount" && echo "${verb}"

[ -d ${mount_dir} ] || mkdir ${mount_dir}

if [ $( grep -c ${mount_dir} /etc/fstab ) -eq 0 ]; then

  echo "${az}.${fs_id}.efs.${region}.amazonaws.com:/ ${mount_dir} nfs4 nfsvers=4.1 0 0" >> /etc/fstab

fi



verb="mounting filesystem" && echo "${verb}"

#output=$( mount ${mount_dir} 2>&1 ) || bail "${verb}" "${output}"

if [ $( mount | grep -c ${mount_dir} ) -eq 0 ]; then

  verb="mounting filesystem" && echo "${verb}"

  output=$( mount ${mount_dir} 2>&1 ) || bail "${verb}" "${output}"

fi




if [ -d ${mount_dir}/jenkins ]; then

  verb="symlinking jenkins directory" && echo "${verb}"

  output=$( ln -s /efs/jenkins /var/lib/jenkins 2>&1 ) || bail "${verb}" "${output}"

  output=$( service jenkins restart 2>&1 ) || bail "${verb}" "${output}"

else

  verb="creating and symlinking jenkins directory" && echo "${verb}"

  output=$( mkdir ${mount_dir}/jenkins && ln -s ${mount_dir}/jenkins /var/lib/jenkins 2>&1 ) || bail "${verb}" "${output}"

fi

