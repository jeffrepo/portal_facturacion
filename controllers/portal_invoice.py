from odoo import http
from odoo.http import request
import re

class PortalInvoiceXml(http.Controller):

    @http.route(['/my/invoices/download_xml/<int:invoice_id>'], type='http', auth="public", website=True)
    def download_xml(self, invoice_id, **kw):
        # 1. Buscar la factura (con sudo para evitar problemas de permisos en portal)
        invoice = request.env['account.move'].sudo().browse(invoice_id)
        if not invoice.exists():
            return request.not_found()

        # 2. Limpiar el nombre como mencionaste (ej: INV/2023/001 -> INV2023001)
        clean_name = re.sub(r'[^a-zA-Z0-9]', '', invoice.name)

        # 3. Buscar el adjunto
        # Filtramos por el ID de la factura y que el nombre contenga el texto limpio y sea .xml
        attachment = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'account.move'),
            ('res_id', '=', invoice.id),
            ('name', 'ilike', clean_name),
            ('name', 'ilike', '.xml')
        ], limit=1)

        if not attachment:
            # Fallback: buscar solo por nombre si no está vinculado correctamente por res_id
            attachment = request.env['ir.attachment'].sudo().search([
                ('name', 'ilike', clean_name),
                ('name', 'ilike', '.xml')
            ], limit=1)

        if attachment:
            return request.make_response(
                attachment.raw,
                headers=[
                    ('Content-Type', 'application/xml'),
                    ('Content-Disposition', f'attachment; filename={attachment.name}')
                ]
            )
        
        return "Archivo XML no encontrado."