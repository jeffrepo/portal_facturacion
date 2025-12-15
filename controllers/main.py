# -*- coding: utf-8 -*-

import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class PortalFacturacionController(http.Controller):

    # 1. RUTA: /portal/facturacion/buscar
    @http.route('/portal/facturacion/buscar', type='http', auth='public', methods=['POST'], csrf=False, website=True)
    def buscar_pedido(self, **post):
        numero = post.get('order_number')
        _logger.info("Pedido recibido: %s", numero)

        order = request.env['pos.order'].sudo().search([('pos_reference', '=', numero)], limit=1)

        if order:
            if order.account_move:
                invoice = order.account_move
                try:
                    share_action = invoice.sudo().with_context(
                        active_model='account.move',
                        active_id=invoice.id,
                        active_ids=[invoice.id]
                    ).action_share()
                    
                    if not invoice.access_token:
                        invoice.sudo()._portal_ensure_token()
                    
                    portal_url = invoice.get_portal_url()
                    print(f"URL del portal generada: {portal_url}")
                    
                    return request.redirect(portal_url)
                    
                except Exception as e:
                    print(f"Error en action_share: {e}")
                    if not invoice.access_token:
                        invoice.sudo()._portal_ensure_token()
                    
                    fallback_url = f"/my/invoices/{invoice.id}?access_token={invoice.access_token}"
                    print(f"Usando URL de fallback: {fallback_url}")
                    return request.redirect(fallback_url)

            else:    
                return request.redirect('/portal/facturacion/identificar_cliente/%s' % order.id)
        else:
            return request.render("portal_facturacion.portal_facturacion_no_encontrado", {
                "numero": numero,
            })

    @http.route('/portal/facturacion/identificar_cliente/<int:order_id>', type='http', auth='public', website=True)
    def identificar_cliente(self, order_id, **kwargs):
        """
        Muestra un formulario simple para ingresar solo el RFC.
        """
        order = request.env['pos.order'].sudo().browse(order_id)
        if not order:
            return request.redirect('/portal/facturacion')

        return request.render("portal_facturacion.portal_facturacion_identificar_cliente", {
            "order": order,
        })


    @http.route('/portal/facturacion/procesar_rfc', type='http', auth='public', methods=['POST'], csrf=False, website=True)
    def procesar_rfc(self, **post):
        """
        Recibe el RFC, busca el cliente y redirige a detalle_pedido (con o sin partner_id).
        """
        order_id = post.get('order_id')
        rfc = post.get('rfc', '').upper().strip()

        if not rfc or not order_id:
            return request.redirect('/portal/facturacion')

        # Buscar cliente (res.partner) por RFC (vat)
        partner = request.env['res.partner'].sudo().search([('vat', '=', rfc)], limit=1)
        
        if partner:
            # Cliente encontrado: Redirigir a detalle_pedido y pasar el partner_id
            return request.redirect('/portal/facturacion/pedido/%s?partner_id=%s' % (order_id, partner.id))
        else:
            # Cliente NO encontrado: Redirigir a detalle_pedido sin partner_id
            return request.redirect('/portal/facturacion/pedido/%s' % order_id)


    @http.route('/portal/facturacion/pedido/<int:order_id>', type='http', auth='public', website=True)
    # Recibir partner_id como argumento opcional desde el querystring
    def detalle_pedido(self, order_id, partner_id=None, **kwargs):
        order = request.env['pos.order'].sudo().browse(order_id)
        partner = False
        
        # Si se pasa un partner_id, se carga el objeto res.partner
        if partner_id:
            partner = request.env['res.partner'].sudo().browse(int(partner_id))
            
        print(f"order company_id {order.company_id} \n")
        
        # Buscamos todos los paises, pero prefiltramos al de la compañía para la vista inicial
        countries = request.env['res.country'].sudo().search([])
        states = request.env['res.country.state'].sudo().search([('country_id', '=', order.company_id.country_id.id)])
        
        # payment_method = request.env['l10n_mx_edi.payment.method'].sudo().search([])
        # 1. Obtener el modelo del contacto res.partner)
        ResPartner = request.env['res.partner'].sudo()

        # 2. Obtener los valores del campo l10n_mx_edi_fiscal_regime
        #    El resultado es un diccionario, el valor que necesitamos es 'selection'
        l10n_mx_edi_fiscal_regime_selection = ResPartner.fields_get(['l10n_mx_edi_fiscal_regime'])
        # La lista de tuplas (valor, etiqueta) está en la clave 'l10n_mx_edi_fiscal_regime' y luego 'selection'
        fiscal_regime_usage_options = l10n_mx_edi_fiscal_regime_selection['l10n_mx_edi_fiscal_regime']['selection']

        # 1. Obtener el modelo de factura (account.move)
        AccountMove = request.env['account.move'].sudo()
        
        # 2. Obtener los valores del campo l10n_mx_edi_usage
        #    El resultado es un diccionario, el valor que necesitamos es 'selection'
        l10n_mx_edi_usage_selection = AccountMove.fields_get(['l10n_mx_edi_usage'])
        # La lista de tuplas (valor, etiqueta) está en la clave 'l10n_mx_edi_usage' y luego 'selection'
        cfdi_usage_options = l10n_mx_edi_usage_selection['l10n_mx_edi_usage']['selection']

        # Obtener los valores de selección para Uso de CFDI
        AccountMove = request.env['account.move'].sudo()
        l10n_mx_edi_usage_selection = AccountMove.fields_get(['l10n_mx_edi_usage'])
        cfdi_usage_options = l10n_mx_edi_usage_selection['l10n_mx_edi_usage']['selection']
        
        # print(f"states {states}, payment_method, {payment_method}")
        print(f"tax_positions {fiscal_regime_usage_options} \n")

        return request.render("portal_facturacion.portal_facturacion_detalle", {
            "order": order,
            "partner": partner,  # ¡Pasamos el objeto partner!
            "countries": countries,
            "states": states,
            # "payment_method": payment_method,
            "fiscal_regime_usage_options": fiscal_regime_usage_options,
            "cfdi_usage_options": cfdi_usage_options,
        })
    
    @http.route('/portal/facturacion/crear_factura', type='http', auth='public', methods=['POST'], csrf=False, website=True)
    def create_invoice(self, order_id, company_name, r_f_C, zip, street, ext, int, cologne, city, state_id, country_id, l10n_mx_edi_usage, l10n_mx_edi_fiscal_regime, **kwargs):
        print("\n========== INICIANDO PROCESO DE FACTURACIÓN ==========\n")
        print(f"Order ID recibido: {order_id} regimen fiscal {l10n_mx_edi_fiscal_regime}")

        order_found = request.env['pos.order'].sudo().search([('id', '=', order_id)], limit=1)
        country_found = request.env['res.country'].sudo().search([('id', '=', country_id)])
        state_found = request.env['res.country.state'].sudo().search([('id', '=', state_id)])
        
        print(f"Order encontrada: {order_found}")
        print(f"País encontrado: {country_found}")
        print(f"Estado encontrado: {state_found}")
        print(f"Datos recibidos -> company_name: {company_name}, zip: {zip}, street: {street}, city: {city}\n")

        # 1. Buscar o crear partner
        if company_name:
            partner = request.env['res.partner'].sudo().search([('vat', '=', r_f_C)], limit=1)

            if partner:
                print(f"Partner existente encontrado: {partner.id} - {partner.name}")
                order_found.write({'partner_id': partner.id})
                partner.write({
                    'name': company_name,
                    'zip': zip,
                    'street': street,
                    'city': city,
                    'state_id': state_found.id,
                    'country_id': country_found.id,
                    'company_id': order_found.company_id.id,
                    'l10n_mx_edi_colony': cologne,
                    'l10n_mx_edi_fiscal_regime': l10n_mx_edi_fiscal_regime,
                })
            else:
                print("Partner NO existe, creando uno nuevo...")
                new_partner_vals = {
                    'name': company_name,
                    'vat': r_f_C,
                    'zip': zip,
                    'street': street,
                    'city': city,
                    'state_id': state_found.id,
                    'country_id': country_found.id,
                    'company_id': order_found.company_id.id,
                    'l10n_mx_edi_colony': cologne,
                    'l10n_mx_edi_fiscal_regime': l10n_mx_edi_fiscal_regime,
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
                order_found.account_move.l10n_mx_edi_usage = l10n_mx_edi_usage
                print("→ Validando factura…")
                print(f"Estado de la factura {order_found.account_move.state}")
                if order_found.account_move.state == 'draft':
                    order_found.account_move.action_post()
                    if order_found.account_move.state == 'post':
                        order_found.account_move.process_edi_invoices()
                else:
                    print(f"Factura validada correctamente. ID: {order_found.account_move.id}")
            else:
                print("⚠ ERROR: La factura no se generó correctamente.")
        
        # 4. Redirigir a vista previa de factura
        invoice = order_found.account_move

        if invoice:
            print(f"\nFactura encontrada para vista previa: {invoice.id}")
            
            try:
                # SOLUCIÓN: Usar with_context para proporcionar el contexto necesario
                # Necesitamos simular un contexto con active_id y active_model
                share_action = invoice.sudo().with_context(
                    active_model='account.move',
                    active_id=invoice.id,
                    active_ids=[invoice.id]
                ).action_share()
                
                # El resultado de action_share() es un diccionario con la acción de ventana
                # Pero necesitamos la URL real del portal
                if not invoice.access_token:
                    # Asegurar que tiene token de acceso
                    invoice.sudo()._portal_ensure_token()
                
                # Generar la URL del portal correctamente
                # Usar get_portal_url() que ya maneja los tokens
                portal_url = invoice.get_portal_url()
                print(f"URL del portal generada: {portal_url}")
                
                # Redirigir al portal
                return request.redirect(portal_url)
                
            except Exception as e:
                print(f"Error en action_share: {e}")
                # Fallback seguro
                if not invoice.access_token:
                    invoice.sudo()._portal_ensure_token()
                
                # Usar método directo para obtener URL
                fallback_url = f"/my/invoices/{invoice.id}?access_token={invoice.access_token}"
                print(f"Usando URL de fallback: {fallback_url}")
                return request.redirect(fallback_url)

        print("\n⚠ No se pudo obtener la factura. Redirigiendo al portal de búsqueda.")
        return request.redirect('/portal/facturacion/buscar')   
    
