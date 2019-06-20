import os
import re

from constant import docker
from helper import common
from service.environment_source.env_source import EnvSource

class VaultSource(EnvSource):
  def __init__(self, service, certs_volume_name, certs_path):
    """
    Create a VaultSource

    :param certs_volume_name: Name of the volume containing service certificate
    :type  certs_volume_name: str

    :param certs_path: Where the service certificate directory is located,
      relative to the volume's root
    :type  certs_path: str
    """

    super().__init__(service)

    self.certs_volume_name = certs_volume_name
    self.certs_path = certs_path

  def parse(self, definition, volume_name=None, volume_mount_path='/vault_secrets'):
    """
    Parse Vault environment configuration from .services.d/<service>/config<env>.yml

    :param definition: A dictionary containing definition of Vault environment
      artifacts. See example in sv/src/template/service/config/env_config.yml.j2
      in the `artifacts.vault` object
    :type  definition: dict

    :key  volume_name: Volume name to store Vault secrets in
    :type volume_name: str

    :key  volume_mount_path: Absolute path to where the volume should be mounted
      in the initContainer and sidecar container
    :type volume_mount_path: str

    :returns: List of Kubernetes configuration overrides. Each configuration
      override is a dict that contain three fields:
        - type: the kind of Kubernetes configuration to override. Currently
            there are three valid values: configmap, deployment, and service
        - override_path: list of strings that specifies the path where the
            configuration will be overriden. See the `path_a` argument of
            `dict_merge()` in `common.py`
        - spec: the specification that will override (or extend) the
            configurations in `override_path`
    :rtype: list[dict]
    """

    # Default volume name to store Vault secrets in
    if volume_name == None:
      volume_name = '{}-{}-vault-volume'.format(
        self.service.service_name,
        self.service.environment,
      )

    # Vault URL and assumed role
    vault_url = definition['url']
    vault_role = definition['role']

    # The service blueprint prefix
    pkictl_blueprint_prefix = common.dict_get(
      self.service.config,
      ['pki', 'pkictl_blueprint_prefix'],
      default=self.service.service_name
    )

    # The service blueprint name for this service as registered to PKICTL
    pkictl_service_blueprint = '{}-{}'.format(
      pkictl_blueprint_prefix,
      self.service.environment
    )

    # VaultSC image
    vaultsc_image = '{}/infra/vaultsc:latest'.format(docker.REGISTRY['DEFAULT'])

    # PKICTL certificate paths. These certificate will be provided by PKICTL
    # Service Certificate InitContainer
    cert_path = '/usr/share/pki/certs/service/{0}/{0}.crt'.format(pkictl_service_blueprint)
    key_path = '/usr/share/pki/certs/service/{0}/.private/{0}.key'.format(pkictl_service_blueprint)
    cacert_path = '/usr/share/pki/certs/service/{0}/{0}-ca-chain.crt'.format(pkictl_service_blueprint)

    # Where should we store the VAULTSC manifest file generated by the
    # InitContainer
    manifest_path = '{}/manifest.json'.format(volume_mount_path)

    # This is the VAULTSC init container which will fetch secrets from Vault
    # before the main container starts. Will be appended into
    # Deployment.spec.template.spec.initContainers
    vaultsc_init_container = {
      'args': [
        'one-time',
        '--url', vault_url,
        '--role', vault_role,
        '--cert', cert_path,
        '--key', key_path,
        '--cacert', cacert_path,
        '--manifest', manifest_path
      ],
      'image': vaultsc_image,
      'name': 'vaultsc-init',
      'volumeMounts': [
        {
          'name': volume_name,
          'mountPath': volume_mount_path
        },
        {
          'name': self.certs_volume_name,
          'mountPath': os.path.join('/usr/share/pki/certs/service', pkictl_service_blueprint),
          'subPath': os.path.join(self.certs_path, pkictl_service_blueprint)
        }
      ]
    }

    # This is the VAULTSC sidecar container which will renew leases created
    # by the init container. Will be appended into
    # Deployment.spec.template.spec.containers
    sidecar_container = {
      'args': ['agent', '--manifest', manifest_path],
      'image': vaultsc_image,
      'name': 'vaultsc',
      'volumeMounts': [
        {
          'name': volume_name,
          'mountPath': volume_mount_path
        },
        {
          'name': self.certs_volume_name,
          'mountPath': os.path.join('/usr/share/pki/certs/service', pkictl_service_blueprint),
          'subPath': os.path.join(self.certs_path, pkictl_service_blueprint)
        }
      ]
    }

    # This in-memory volume will contain secrets fetched from Vault and will be
    # appended into the Volumes list in Deployment.spec.template.spec.volumes
    volume = {
      'name': volume_name,
      'emptyDir': {
        'medium': 'Memory',
        'sizeLimit': '5Mi'
      }
    }

    # This list contains what files should be mounted to the service's working
    # directory. Will extend the VolumeMounts list defined in
    # Deployment.spec.template.spec.containers[0].volumeMounts
    volume_mounts = []

    # This list will be appended into the main container args list in
    # Deployment.spec.template.spec.containers[0].args
    main_container_args = []

    # List of Vault secrets to fetch
    vault_secrets = definition.get('secrets', []) or []

    for index, secret in enumerate(vault_secrets):
      secret_path = secret['path']
      secret_type = secret.get('type', 'kv')
      secret_definition = secret.get(secret_type, {})

      # We'll need to sanitize the Vault secret path as we'll use this path
      # as filename to store the fetched secret.
      # Index is appended so the same secret can be mounted more than once
      # without conflict
      sanitized_secret_path = '{}-{}'.format(
        re.sub('[^-._a-zA-Z0-9]', '_', secret_path),
        index
      )

      secret_filepath = os.path.join(volume_mount_path, sanitized_secret_path)

      mount_type = secret.get('mount',  {}).get('type', 'env')

      # Where should the secret be mounted on the main service container
      absolute_secret_mount_path = None

      if mount_type == 'env':
        relative_secret_mount_path = sanitized_secret_path

        # env-type environment artifact won't be loaded directly by the service,
        # so it's safe to mount the file not in its working directory
        absolute_secret_mount_path = os.path.join(
          volume_mount_path,
          relative_secret_mount_path
        )

        # Load the file as environment variables through svctl run --env-file
        # flag
        main_container_args += ['--env-file', absolute_secret_mount_path]
      elif mount_type == 'file':
        relative_secret_mount_path = secret['mount']['path']

        # Mount the file directly inside the service's working directory
        absolute_secret_mount_path = os.path.join(
          self.service.base_image_workdir,
          relative_secret_mount_path
        )

      volume_mounts.append({
        'name': volume_name,
        'mountPath': absolute_secret_mount_path,
        'subPath': sanitized_secret_path
      })

      # Add VAULTSC arguments
      if secret_type == 'kv':
        vaultsc_init_container['args'] += self._kv(secret_path, secret_definition, secret_filepath)
      elif secret_type == 'db':
        vaultsc_init_container['args'] += self._db(secret_path, secret_definition, secret_filepath)

    # There are no secrets, we don't need to override the Kubernetes YAMLs with
    # all this Vault stuff
    if len(vault_secrets) == 0:
      return []

    return [
      {
        'type': 'deployment',
        'override_path': ['spec', 'template', 'spec', 'initContainers'],
        'spec': [vaultsc_init_container]
      },
      {
        'type': 'deployment',
        'override_path': ['spec', 'template', 'spec', 'containers'],
        'spec': [sidecar_container]
      },
      {
        'type': 'deployment',
        'override_path': ['spec', 'template', 'spec', 'volumes'],
        'spec': [volume]
      },
      {
        'type': 'deployment',
        'override_path': ['spec', 'template', 'spec', 'containers', 0, 'volumeMounts'],
        'spec': volume_mounts
      },
      {
        'type': 'deployment',
        'override_path': ['spec', 'template', 'spec', 'containers', 0, 'args'],
        'spec': main_container_args
      }
    ]

  def _kv(self, path, definition, filepath):
    """
    Returns VAULSC argument for a KV secret

    :param path: Path to the KV secret
    :type  path: str

    :param definition: Definition of the KV secret. Contains one optional field
      'key'
    :type  definition: dict

    :param filepath: Path to the file which will contain the KV secret
    :type  filepath: str

    :returns: VAULTSC argument
    :rtype: list[str]
    """

    key = definition.get('key', '')

    return [
      '--kv',
      '{}::{}::{}'.format(path, key, filepath)
    ]

  def _db(self, path, definition, filepath):
    """
    Returns VAULSC argument for a DB secret

    :param path: Path to the DB secret
    :type  path: str

    :param definition: Definition of the DB secret. Contains 'user_key' and
      'pass_key' fields
    :type  definition: dict

    :param filepath: Path to the file which will contain the DB secret
    :type  filepath: str

    :returns: VAULTSC argument
    :rtype: list[str]
    """

    user_key = definition.get('user_key', '')
    pass_key = definition.get('pass_key', '')

    return [
      '--db',
      '{}::{}::{}::{}'.format(path, user_key, pass_key, filepath)
    ]
