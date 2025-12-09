# -*- coding: utf-8 -*-

import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class PortalFacturacionController(http.Controller):

    @http.route('/portal/facturacion/buscar', type='http', auth='public', methods=['POST'], csrf=False, website=True)
    def buscar_pedido(self, **post):
        numero = post.get('order_number')
        _logger.info("Pedido recibido: %s", numero)

        order = request.env['pos.order'].sudo().search([('pos_reference', '=', numero)], limit=1)

        if order:
            if order.account_move:
                print(f"\nFactura encontrada para vista previa: {order.account_move.id}")
                print(f"Access Token: {order.account_move.access_token}")
                preview_url = f"/my/invoices/{order.account_move.id}?access_token={order.account_move.access_token}"
                print(f"Redirigiendo a vista previa: {preview_url}\n")

                return request.redirect(preview_url)
            else:    
                # Redirigir a la página de detalle del pedido
                return request.redirect('/portal/facturacion/pedido/%s' % order.id)
        else:
            # Mostrar página con mensaje de error
            return request.render("portal_facturacion.portal_facturacion_no_encontrado", {
                "numero": numero,
            })

    @http.route('/portal/facturacion/pedido/<int:order_id>', type='http', auth='public', website=True)
    def detalle_pedido(self, order_id, **kwargs):
        order = request.env['pos.order'].sudo().browse(order_id)
        print(f"order company_id {order.company_id} \n")
        countries = request.env['res.country'].sudo().search([('id', '=', order.company_id.country_id.id)])
        states = request.env['res.country.state'].sudo().search([('country_id', '=', order.company_id.country_id.id)])
        payment_method = request.env['l10n_mx_edi.payment.method'].sudo().search([])
        fiscal_regime = request.env['l10n_mx_edi.customs.regime'].sudo().search([])
        print(f"states {states}, payment_method, {payment_method}")
        print(f"tax_positions {fiscal_regime} \n")

        return request.render("portal_facturacion.portal_facturacion_detalle", {
            "order": order,
            "countries": countries,
            "states": states,
            "payment_method":payment_method,
            "fiscal_regime":fiscal_regime,
        })
    
    @http.route('/portal/facturacion/crear_factura', type='http', auth='public', methods=['POST'], csrf=False, website=True)
    def create_invoice(self, order_id, company_name, r_f_C, zip, street, ext, int, cologne, city, state_id, country_id, cfdi, payment_method_id, fiscal_regime_id, **kwargs):
        print("\n========== INICIANDO PROCESO DE FACTURACIÓN ==========\n")
        print(f"Order ID recibido: {order_id} regimen fiscal {fiscal_regime_id}")

        order_found = request.env['pos.order'].sudo().search([('id', '=', order_id)], limit=1)
        country_found = request.env['res.country'].sudo().search([('id', '=', country_id)])
        state_found = request.env['res.country.state'].sudo().search([('id', '=', state_id)])
        

        print(f"Order encontrada: {order_found}")
        print(f"País encontrado: {country_found}")
        print(f"Estado encontrado: {state_found}")
        # print(f"Posición fiscal encontrada: {fiscal_position}")
        print(f"Datos recibidos -> company_name: {company_name}, zip: {zip}, street: {street}, city: {city}\n")

        # 1. Buscar o crear partner
        if company_name:
            partner = request.env['res.partner'].sudo().search([('name', '=', company_name)], limit=1)

            if partner:
                print(f"Partner existente encontrado: {partner.id} - {partner.name}")
                order_found.write({'partner_id': partner.id})
            else:
                print("Partner NO existe, creando uno nuevo...")
                new_partner_vals = {
                    'name': company_name,
                    'zip': zip,
                    'street': street,
                    'city': city,
                    'state_id': state_found.id,
                    'country_id': country_found.id,
                    'company_id': order_found.company_id.id,
                    'l10n_mx_edi_fiscal_regime': fiscal_regime_id,
                }

                print(f"Valores del nuevo partner: {new_partner_vals}")
                partner = request.env['res.partner'].sudo().create(new_partner_vals)
                print(f"Partner creado con ID: {partner.id}")

                order_found.write({'partner_id': partner.id})
                print(f"Partner asignado a la orden POS: {partner.id}")

            # 2. Crear factura desde POS
            print("\n→ Creando factura desde POS…")
            order_found.action_pos_order_invoice()
            request.env.cr.commit()

            print(f"Factura generada: {order_found.account_move}")

            # 3. Validar factura (post)
            if order_found.account_move:
                order_found.account_move.l10n_mx_edi_payment_method_id = payment_method_id
                print("→ Validando factura…")
                print(f"Estado de la factura {order_found.account_move.state}")
                if order_found.account_move.state == 'draft':
                    order_found.account_move.action_post()
                else:
                    print(f"Factura validada correctamente. ID: {order_found.account_move.id}")
            else:
                print("⚠ ERROR: La factura no se generó correctamente.")
        
        # 4. Redirigir a vista previa de factura
        invoice = order_found.account_move

        if invoice:
            print(f"\nFactura encontrada para vista previa: {invoice.id}")
            print(f"Access Token: {invoice.access_token}")
            preview_url = f"/my/invoices/{invoice.id}?access_token={invoice.access_token}"
            print(f"Redirigiendo a vista previa: {preview_url}\n")

            return request.redirect(preview_url)

        print("\n⚠ No se pudo obtener la factura. Redirigiendo al portal de búsqueda.")
        return request.redirect('/portal/facturacion/buscar')



    
    
