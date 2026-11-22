"""Render the Container Apps YAML (JSON is valid YAML) into a private temporary file."""
import json
import os
import re
import sys


def render(service, env):
    if service not in ('household', 'fairness'):
        raise ValueError('Unknown service')
    sha = env['GITHUB_SHA']
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('Deployment requires a full commit SHA')
    port = 5000 if service == 'household' else 5001
    variables = [
        {'name': 'PORT', 'value': str(port)},
        {'name': 'DATABASE_URL', 'secretRef': 'database-url'},
        {'name': 'AUTH_SECRET', 'secretRef': 'auth-secret'},
        {'name': 'CORS_ORIGIN', 'value': env['UI_ORIGIN']},
        {'name': 'GIT_SHA', 'value': sha},
        {'name': 'DB_CONNECT_RETRY_S', 'value': '90'},
    ]
    if service == 'fairness':
        variables += [
            {'name': 'HOUSEHOLD_URL', 'value': env['HOUSEHOLD_URL']},
            {'name': 'HOUSEHOLD_TIMEOUT_S', 'value': '5'},
        ]
    else:
        variables.append({'name': 'HOUSEHOLD_TIMEZONE', 'value': 'Europe/Paris'})
    return {
        'name': env['PREFIX'] + '-' + service,
        'location': env['LOCATION'],
        'properties': {
            'managedEnvironmentId': env['ENVIRONMENT_ID'],
            'configuration': {
                'activeRevisionsMode': 'Single',
                'secrets': [
                    {'name': 'database-url', 'value': env[service.upper() + '_DATABASE_URL']},
                    {'name': 'auth-secret', 'value': env['AUTH_SECRET']},
                ],
                'ingress': {
                    'external': True, 'targetPort': port, 'transport': 'auto',
                    'allowInsecure': False,
                },
            },
            'template': {
                # Express manages revisions and traffic automatically. Identify
                # deployments by the immutable image tag and GIT_SHA instead.
                'scale': {'minReplicas': 0, 'maxReplicas': 1, 'rules': [{
                    'name': 'http', 'http': {'metadata': {'concurrentRequests': '10'}},
                }]},
                'containers': [{
                    'name': service,
                    'image': 'ghcr.io/' + env['GITHUB_REPOSITORY_OWNER'].lower() + '/housemate-' + service + ':' + sha,
                    'resources': {'cpu': 0.5, 'memory': '1Gi'},
                    'env': variables,
                    'probes': [
                        {'type': 'Startup', 'httpGet': {'path': '/health', 'port': port},
                         'periodSeconds': 5, 'timeoutSeconds': 5, 'failureThreshold': 36},
                        {'type': 'Readiness', 'httpGet': {'path': '/health', 'port': port},
                         'periodSeconds': 30, 'timeoutSeconds': 5, 'failureThreshold': 3},
                        # DB outages must not restart a healthy process in a loop.
                        {'type': 'Liveness', 'tcpSocket': {'port': port},
                         'periodSeconds': 30, 'timeoutSeconds': 5, 'failureThreshold': 3},
                    ],
                }],
            },
        },
    }


if __name__ == '__main__':
    # Caller creates this in a mode-700 temp directory, with umask 077.
    with open(sys.argv[2], 'w') as stream:
        json.dump(render(sys.argv[1], os.environ), stream)
