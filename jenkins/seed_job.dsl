def job_name = "${program}-${domain}-${stage}-v${version}-job"

job( job_name ) {
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
    git( "${repo_url}", "${branch}" )
  }
  triggers {
    scm( 'H/2 * * * *' )
  }
  wrappers {
    preBuildCleanup()
  }
  steps {
    virtualenvBuilder {
      pythonName('System-CPython-2.7')
      clear( true )
      home( '' )
      systemSitePackages( false )
      nature( 'shell' )
      command( 'pip install boto3 \n\
REGION=${region} \n\
PROGRAM=${program} \n\
DOMAIN=${domain} \n\
STAGE=${stage} \n\
VERSION=${version} \n\
BUCKET=${bucket} \n\
python /opt/jenkins-stack/bin/update_stack.py \\\n\
  -r ${REGION} \\\n\
  -p ${PROGRAM} \\\n\
  -d ${DOMAIN} \\\n\
  -s ${STAGE} \\\n\
  -v ${VERSION} \\\n\
  -c ${WORKSPACE} \\\n\
  -b ${BUCKET} \\\n\
  -n ${PROGRAM}-${DOMAIN}-${STAGE}-v${VERSION}-stack \\\n\
  -e ${VIRTUAL_ENV}/lib/python2.7/site-packages')
      ignoreExitCode( false )
    }
  }
}
