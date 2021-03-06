import os
import logging
import base64
from twisted.internet import defer, reactor
from lbrynet.core.client.DHTPeerFinder import DHTPeerFinder
from lbrynet.core.server.DHTHashAnnouncer import DHTHashAnnouncer
from lbrynet.core.PeerManager import PeerManager
from lbrynet.core.BlobManager import DiskBlobManager
from lbrynet import conf
from lbrynet.dht.node import Node
from lighthouse.conf import LBRYID

log = logging.getLogger(__name__)


class StreamAvailabilityManager(object):
    def __init__(self, storage):
        self.storage = storage
        self.lbryid = base64.decodestring(LBRYID)
        self.peer_manager = None
        self.peer_finder = None
        self.dht_node = None
        self.hash_announcer = None
        self.blob_manager = None
        self.dht_node_port = conf.settings['dht_node_port']
        self.blob_data_dir = conf.settings['data_dir']
        self.blob_dir = os.path.join(self.blob_data_dir, conf.settings['BLOBFILES_DIR'])
        self.peer_port = conf.settings['peer_port']
        self.known_dht_nodes = conf.settings['known_dht_nodes']
        self.external_ip = '127.0.0.1'

    def start(self):
        if self.peer_manager is None:
            self.peer_manager = PeerManager()

        def match_port(h, p):
            return h, p

        def join_resolved_addresses(result):
            addresses = []
            for success, value in result:
                if success is True:
                    addresses.append(value)
            return addresses

        def start_dht(addresses):
            log.info("Starting the dht")
            log.info("lbry id: %s", base64.encodestring(self.lbryid).strip("\n"))
            self.dht_node.joinNetwork(addresses)
            self.peer_finder.run_manage_loop()
            self.hash_announcer.run_manage_loop()

        ds = []

        for host, port in self.known_dht_nodes:
            d = reactor.resolve(host)
            d.addCallback(match_port, port)
            ds.append(d)

        if self.dht_node is None:
            self.dht_node = Node(
                udpPort=self.dht_node_port,
                lbryid=self.lbryid,
                externalIP=self.external_ip
            )
        if self.peer_finder is None:
            self.peer_finder = DHTPeerFinder(self.dht_node, self.peer_manager)
        if self.hash_announcer is None:
            self.hash_announcer = DHTHashAnnouncer(self.dht_node, self.peer_port)
        if self.blob_manager is None:
            self.blob_manager = DiskBlobManager(
                self.hash_announcer, self.blob_dir, self.blob_data_dir)

        d1 = defer.DeferredList(ds)
        d1.addCallback(join_resolved_addresses)
        d1.addCallback(start_dht)
        d2 = self.blob_manager.setup()
        dl = defer.DeferredList([d1, d2], fireOnOneErrback=True, consumeErrors=True)
        return dl

    def stop(self):
        log.info("Shutting down availability manager")
        ds = []
        if self.blob_manager is not None:
            ds.append(defer.maybeDeferred(self.blob_manager.stop))
        if self.dht_node is not None:
            ds.append(defer.maybeDeferred(self.dht_node.stop))
        if self.peer_finder is not None:
            ds.append(defer.maybeDeferred(self.peer_finder.stop))
        if self.hash_announcer is not None:
            ds.append(defer.maybeDeferred(self.hash_announcer.stop))
        return defer.DeferredList(ds)

    def get_peers_for_hash(self, blob_hash):
        return self.peer_finder.find_peers_for_blob(blob_hash)
