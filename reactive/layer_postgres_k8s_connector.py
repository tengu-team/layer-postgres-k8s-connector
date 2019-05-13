#!/usr/bin/env python3
# Copyright (C) 2017  Qrama, developed by Tengu-team
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import yaml
import base64
import charms.leadership
from charmhelpers.core.templating import render
from charmhelpers.core import unitdata
from charmhelpers.core.hookenv import status_set, config, application_name, leader_get, leader_set, is_leader, unit_private_ip
from charms.reactive import when, when_not, when_not, set_flag, clear_flag, when_any
from charms.reactive.relations import endpoint_from_flag


config = config()


########################################################################
# Install
########################################################################
@when_not('endpoint.kubernetes-deployer.available', 'postgres.connected', 'connector.installed')
def missing_http_relation():
    status_set('blocked', 'Waiting for kubernetes-deployer and postgres relation')


@when('postgres.connected')
@when_not('endpoint.kubernetes-deployer.available', 'connector.installed')
def missing_http_relation():
    status_set('blocked', 'Waiting for kubernetes-deployer relation')


@when('endpoint.kubernetes-deployer.available')
@when_not('postgres.connected, connector.installed')
def missing_postgres_relation():
    status_set('blocked', 'Waiting for postgres relation')


########################################################################
# Install and send request
########################################################################

@when('postgres.connected')
@when_not('connector.db.created')
def create_database():
    if not config.get('database'):
        status_set('blocked', 'Waiting for database config')
        return
    if is_leader():
        status_set('maintenance', 'Setting up database on the external PostgreSQL server.')
        pgsql = endpoint_from_flag('postgres.connected')
        pgsql.set_database(config.get('database'))
    else:
        status_set('active', 'Ready (not leader!)')
    current_workers = leader_get().get('workers', [])
    current_workers.append(unit_private_ip())
    leader_set({'workers': current_workers})
    set_flag('connector.db.created')


@when('postgres.master.available',
      'connector.db.created',
      'leadership.is_leader')
@when_not('connector.data.retrieved')
def get_postgres_data():
    status_set('maintenance', 'Retrieving postgres data')
    pgsql = endpoint_from_flag('postgres.master.available')
    unitdata.kv().set('pg_user', pgsql.master.user)
    unitdata.kv().set('pg_password', pgsql.master.password)
    unitdata.kv().set('pg_host', pgsql.master.host)
    unitdata.kv().set('pg_port', pgsql.master.port)
    set_flag('connector.data.retrieved')


@when('endpoint.kubernetes-deployer.available',
      'connector.data.retrieved',
      'leadership.is_leader')
@when_not('connector.installed')
def install():
    status_set('maintenance', 'Sending secret request to k8s')
    k8s_deployer = endpoint_from_flag('endpoint.kubernetes-deployer.available')
    endpoints = k8s_deployer.get_worker_ips()
    if not endpoints or len(endpoints) == 0:
        status_set('blocked', 'Waiting for Kubernetes deployer to be ready')
        return
    secret_context = {'username': base64.b64encode(unitdata.kv().get('pg_user').encode()).decode('utf-8'), 'password': base64.b64encode(unitdata.kv().get('pg_password').encode()).decode('utf-8')}
    secret = render('k8s-secret.yaml', None, secret_context)
    config_context = {'host': unitdata.kv().get('pg_host'),
                      'port': unitdata.kv().get('pg_port'),
                      'database': config.get('database')}
    configmap = render('configmap.yaml', None, config_context)
    k8s_deployer.send_create_request([yaml.load(secret), yaml.load(configmap)])
    status_set('active', 'Ready')
    set_flag('connector.installed')


@when('connector.installed')
@when('endpoint.kubernetes-deployer.new-status')
def status_update():
    endpoint = endpoint_from_flag('endpoint.kubernetes-deployer.new-status')
    status = endpoint.get_status()
    print(status)
    status_set('active', 'Ready, Secret and configmap deployed')
