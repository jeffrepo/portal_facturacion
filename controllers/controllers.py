# -*- coding: utf-8 -*-
# from odoo import http


# class PortalFacturacion(http.Controller):
#     @http.route('/portal_facturacion/portal_facturacion', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/portal_facturacion/portal_facturacion/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('portal_facturacion.listing', {
#             'root': '/portal_facturacion/portal_facturacion',
#             'objects': http.request.env['portal_facturacion.portal_facturacion'].search([]),
#         })

#     @http.route('/portal_facturacion/portal_facturacion/objects/<model("portal_facturacion.portal_facturacion"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('portal_facturacion.object', {
#             'object': obj
#         })