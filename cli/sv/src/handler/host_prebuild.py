from handler import CommandHandler
from handler._parser import PositionalParser
from handler._validator import ServiceValidator
from service import Service

class ServiceHostPrebuild(CommandHandler):
  """
  Run the host pre-build script of a service
  Positional arguments: SERVICE_NAME, ENVIRONMENT
  """

  def __init__(self):
    super(ServiceHostPrebuild, self).__init__(
      parser=PositionalParser('service_name', 'environment'),
      validators=[
        ServiceValidator(service_name='service_name', environment='environment')
      ]
    )

  def _execute(self, kwargs):
    """
    Execute the command

    :param kwargs: Command keyword arguments
    :type  kwargs: dict
    """

    service_name = kwargs['service_name']
    environment = kwargs['environment']

    service = Service(service_name, environment)
    service.host_prebuild()

command = ServiceHostPrebuild()
