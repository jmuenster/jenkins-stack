# AWS Jenkins Cloudformation Stack

This template creates the following:

- a [network stack](https://github.com/jmuenster/vpc-stack)
- an EFS file system
- 3 * EFS mount points
- an ASG of 1 instance, configured to install and run jenkins
- an ELB fronting the ASG
- a lambda function that (optionally) manages an ACM certificate
- an instance profile for the function and ASG instance
- security groups for the ELB and ASG instance

[ <img src="https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png" alt="Launch stack image" style="height: 10;"/> ](https://console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/new?stackName=jenkins-stack&templateURL=https://s3-us-west-2.amazonaws.com/jmuenster-public-templates/jenkins-stack/template.json)


