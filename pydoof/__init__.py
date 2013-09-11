import re
import json

import requests

from pydoof.management import ManagementApiClient
from pydoof.search import SearchApiClient

API_KEY = None
"""
The API key to use when authenticating API requests.

The region must be included: token-region
Example: b42e3ea7c94c93555aa3dcdf2926ead136819518-eu1
"""

CLUSTER_REGION = 'eu1'
""" The amazon region doofinder's cluster is in """

MANAGEMENT_DOMAIN = '%cluster_region%-api.doofinder.com'
""" The management API endpoint to send requests to."""

SEARCH_DOMAIN = '%cluster_region%-search.doofinder.com'
"""The search API endpoint to send search requests to"""

MANAGEMENT_VERSION = '1'
"""The version of server management API"""

SEARCH_VERSION = '4'
"""The version of server search API"""

HTTPS = False
"""Whether or not search request should made throug https"""


class SearchEngine(SearchApiClient, ManagementApiClient):
    """
    SearchEngine's basic api management object

    - CRUD operations to search engine's indexed items
    - processing of the search engine's feeds
    - make search requests
    """

    @classmethod
    def all(cls):
        """
        obtain search engines resources for this token

        Returns:
            A list of search engines.
        """
        search_engines = []

        for hashid, props in self.get_api_root().iteritems():
            search_engines.append(SearchEngine(hashid, name=props['name'],
                                               datatypes=props['items'].keys()))
        return search_engines

    
    def __init__(self, hashid, name=None, datatypes=None, **kwargs):
        self.hashid = hashid 
        self.name = name
        self._datatypes = datatypes
        super(SearchEngine, self).__init__(**kwargs)

    def get_datatypes(self):
        """
        Get a list of searchengine's datatypes

        Returns:
            list of datatypes
            example:
            ['product', 'page']
        """
        
        if not self._datatypes and API_KEY:
            self._datatypes = [props['items'].keys() for hashid, props
                              in self.get_api_root().iteritems()][0]
        return self._datatypes
        
    def items(self, item_type, page=1):
        """
        get paginated indexed items
        
        Args:
            item_type: the type of items . 
            page: the page number.

        Returns:
            array of Item objects
            example:
            [{'title': 'red shoes', 'price': 33.2}, {'title': 'blue shirt', 'price': 23.2}]
        """
        result = self.management_api_call(
            entry_point='%s/items/%s' % (self.hashid, item_type),
            params={'page': page})

        return map(lambda x: Item(x), result['response']['results'])

    def get_item(self, item_type, item_id):
        """
        get details of a specific item
        Args:
            id: value of the identificator field of the item within its type
            item_type: type of the item.
                      if not provided, the search engine's first available datatype is used

        Returns:
            dict representing the item.
        """
        raw_result = self.management_api_call(
            entry_point='%s/items/%s/%s' % (self.hashid, item_type,
                                            item_id))['response']
        return Item(raw_result)

    def add_item(self, item_type, item_description):
        """
        Add an item to the search engine

        Args:
            item_description: dict or pydoof.Item representing the item to be
                              added
                NOTE: if item's id field not present, one will be created
            item_type: type of the item. If not provided, first one available
                       will be used

        Returns:
            the the id of the created_item, on success
        """
        result = self.management_api_call(
            'post', entry_point='%s/items/%s' % (self.hashid, item_type),
            data=json.dumps(item_description))

        return self._obtain_id(result['response']['url'])

    def update_item(self, item_type, item_id, item_description):
        """
        Update an item of the search engine

        Args:
            item_type: type of the item.
            item_id: id of the item to be updated
            item_description: updated data. dict or Item()
                NOTES:
                  - partial updates not implemented yet
                  - description's id will always be set to item_id,
                  no matter what is posted in description content    

        Returns:
            True on success
        """
        result = self.management_api_call(
            'put', data=json.dumps(item_description), 
            entry_point='%s/items/%s/%s' % (self.hashid, item_type, item_id))
        

    def delete_item(self, item_type, item_id):
        """
        delete an item

        Args:
            id: item's unique identificator within its item_type
            item_type: if none the first available datatype is used

        Returns:
            true on success
        """
        result = self.management_api_call(
            'delete', entry_point='%s/items/%s/%s' % (self.hashid, item_type,
                                                      item_id))

        if result['status_code'] == requests.codes.NO_CONTENT:
            return True
        else:
            return False

    def process(self):
        """
        Ask the server to process the search engine's feeds

        Returns:
            (True, task_id) The feed process has been started.
                            <task_id> is the id of the started process
            (False, task_id) There is another feed processing going on.
                             <task_id> is the id of the currently running process
        """
        result = self.management_api_call(
            'post', entry_point='%s/tasks/process' % self.hashid)

        if result['status_code'] == requests.codes.CREATED:
            return (True, self._obtain_id(result['response']['link']))
        if result['status_code'] == request.codes.OK:
            return (False, self._obtain_id(result['response']['link']))

    def info(self, task_id):
        """
        Obtain info about how a process is going

        Returns:
            a dict with the keys 'state' and 'message'
            examples:
            - {'state': 'PROCESSING', 'message': 'Your task is being processed'}
            - {'state': 'SUCCESS', 'message': '1221 items processed'}
            - {'state': 'FAILURE', 'message': 'no data in the feed'}            
        """
        result = self.management_api_call(
            entry_point='%s/tasks/%s' % (self.hashid, task_id))
        
        return result['response']

    def logs(self):
        """
        Obtain logs of the latest feed processing tasks done

        Returns:
            (list) list of dicts representing the logs
            example:[{'date': '2013-07-24T12:37:58.990', 
                     'level': 'ERROR', 
                     'msg': 'Wrong or not existent ...',
                     'log_type': 'log.parser'
                    }, {...}]
        """
        result = self.management_api_call(
            entry_point='%s/tasks/process' % self.hashid)

        return result['response']

    def query(self, query_term, page=1, filters=None, query_name=None, **kwargs):
        """
        Search the elasticsearch index

        Args:
            query_term:  the actual query
            page: page number
            filters: filter definition.
                Example:
                    {'brand': ['nike', 'addidas'],
                    'price': {'from': 2.34, 'to': 12}}
            query_name: instructs doofinder to use only that query type
            options: dict with additional requests parameters
            any other keyword param is added as request parameter

        Returns:
            A dict representing the response

        Raises:
            NotAllowed: if auth is failed.
            BadRequest: if the request is not proper
            WrongREsponse: if server error       
        """
        response = self.search_api_call(self.hashid, query_term, page=page,
                                        filters=filters, query_name=query_name,
                                        **kwargs)

        return response['response']
        
        


    def _obtain_id(self, url):
        """
        Extracs identifactor from an item or task url .

        Args:
            url: item or task resource locator

        Returns:
            the item or task identificator
        """
        url_re = re.compile('/(?P<hashid>\w{32})/(items/\w+|tasks)/(?P<id>[\w-]+)/?$')

        return url_re.search(url).groupdict()['id']


class Item(dict):
    """
    Simple wrapper to add __getattr__ methods to a dict

    >>> it = Item()
    >>> it
    {}
    >>> it['a'] = 'va'
    >>> it.b = 'vb'
    >>> it
    {'a': 'va', 'b': 'vb'}
    """
    def __init__(self, initial_object=None):
        """prepopulate with initial_object"""
        if type(initial_object) == dict:
            self._hidrate(initial_object)
            
    def __getattr__(self, name):
        return self.__getitem__(name)

    def __setattr__(self, name, value):
        self.__setitem__(name, value)

    def _hidrate(self, obj):
        for key, value in obj.iteritems():
            if type(value) == dict:
                value = Item(value)
            if type(value) == list:
                value = map(lambda x: Item(x) if type(x) == dict else x, value)
            self[key] = value
            

