# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 Serpent Consulting Services Pvt. Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# See LICENSE file for full copyright and licensing details.

import logging
import xmlrpc.client

from odoo import api, fields, models

from odoo.addons.queue_job.job import job, related_action
from odoo.addons.connector.exception import IDMissingInBackend
from odoo.addons.component.core import Component

_logger = logging.getLogger(__name__)


class WooShippingZone(models.Model):
    _name = 'woo.shipping.zone'
    _inherit = 'woo.binding'
    _inherits = {'res.country': 'odoo_id'}
    _description = 'Woo Shipping Zone'

    _rec_name = 'name'

    odoo_id = fields.Many2one(
        'res.country',
        string='country',
        required=True,
        ondelete='cascade'
    )
    backend_id = fields.Many2one(
        comodel_name='woo.backend',
        string='Woo Backend',
        store=True,
        readonly=False,
    )
    

    @job(default_channel='root.woo')
    @related_action(action='related_action_unwrap_binding')
    @api.multi
    def export_record(self):
        """ Export Shipping Zones. """
        for rec in self:
            rec.ensure_one()
            with rec.backend_id.work_on(rec._name) as work:
                exporter = work.component(usage='shipping.zone.exporter')
                return exporter.run(self)


class ShippingZone(models.Model):
    _inherit = 'res.country'

    woo_bind_ids = fields.One2many(
        comodel_name='woo.shipping.zone',
        inverse_name='odoo_id',
        string="Woo Bindings",
    )
    #These fields are required for export
    sync_data = fields.Boolean("Synch with Woo?")
    woo_backend_id = fields.Many2one(
        'woo.backend',
        string="WooCommerce Store"
    )


class ShippingZoneAdapter(Component):
    _name = 'woo.shipping.zone.adapter'
    _inherit = 'woo.adapter'
    _apply_on = 'woo.shipping.zone'

    _woo_model = 'shipping/zones'

    def _call(self, method, resource, arguments):
        try:
            return super(ShippingZoneAdapter, self)._call(method, resource, arguments)
        except xmlrpc.client.Fault as err:
            # this is the error in the WooCommerce API
            # when the Shipping Zone does not exist
            if err.faultCode == 102:
                raise IDMissingInBackend
            else:
                raise

    def search(self, method, filters=None, from_date=None, to_date=None):
        """ Search records according to some criteria and return a
        list of ids

        :rtype: list
        """
        if filters is None:
            filters = {}
        WOO_DATETIME_FORMAT = '%Y/%m/%d %H:%M:%S'
        dt_fmt = WOO_DATETIME_FORMAT
        if from_date is not None:
            filters.setdefault('updated_at', {})
            filters['updated_at']['from'] = from_date.strftime(dt_fmt)
        if to_date is not None:
            filters.setdefault('updated_at', {})
            filters['updated_at']['to'] = to_date.strftime(dt_fmt)
        res = self._call(method, 'shipping/zones', [filters] if filters else [{}])
        print("RES--------------------", res)
        # Set shipping zone ids and return it(Due to new WooCommerce REST API)
        zone_ids = list()
        for zone in res: #name
            zone_ids.append(zone.get('id'))
        return zone_ids

    def create(self, data):
        """ Create a record on the external system """
        data = {
            "shipping_zone": data
        }
        return self._call('post', self._woo_model, data)

    def write(self, id, data):
        """ Update records on the external system """
        data = {
            "shipping_zone": data
        }
        return self._call('put', self._woo_model + "/" + str(id),  data)

    def is_woo_record(self, woo_id, filters={}):
        """
        This method is verify the existing record on WooCommerce.
        @param: woo_id : External id (int)
        @param: filters : Filters to check (json)
        @return: result : Response of Woocom (Boolean)
        """
        return self._call('get',self._woo_model + '/' + str(woo_id), filters)