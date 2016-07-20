job('generated-pipeline-test-job') {
  properties {
    buildDiscarder {
      strategy {
        logRotator {
          numToKeepStr('5')
          daysToKeepStr( '-1' )
          artifactDaysToKeepStr( '-1' )
          artifactNumToKeepStr( '-1' )
        }
      }
    }
  }
  scm {
    git( '${repo_url}', '${branch}' )
  }
  triggers {
    scm( 'H/2 * * * *' )
  }
  wrappers {
    preBuildCleanup()
  }
  steps {
    shell( '/opt/jenkins-stack/bin/update_stack.sh \\\n\
      ${WORKSPACE}/cfn/template.json \\\n\
      ${region} \\\n\
      ${WORKSPACE}/tmp/${package_name}-pkg.zip \\\n\
      ${package_name}/${package_name}-pkg.zip \\\n\
      ${s3_bucket} \\\n\
      ${stack_name}' )
  }
}
