@app.route('/generate_heat_loss_report/<batch_id>', methods=['POST'])
def generate_heat_loss_report_route(batch_id):
    """
    Generate professional heat loss report from labeled hot spots.
    
    Step 2: Creates final HTML report with energy-saving recommendations
    
    Optional form parameters:
    - property_address: Property address for report
    - inspector_name: Inspector name for report
    - doc_mode: 'link' to include external link, 'embed' to embed document
    """
    try:
        tenant_id = request.headers.get('X-Tenant-ID', settings.DEFAULT_TENANT)
        property_address = request.form.get('property_address', '')
        inspector_name = request.form.get('inspector_name', '')
        doc_mode = request.form.get('doc_mode', 'link')  # 'link' or 'embed'
        
        report_data = generate_report(
            batch_id,
            property_address=property_address,
            inspector_name=inspector_name,
            doc_mode=doc_mode,
            tenant_id=tenant_id
        )
        
        return jsonify({
            'success': True,
            'message': 'Heat loss report generated successfully',
            'report_url': url_for('view_heat_loss_report', batch_id=batch_id)
        })
    
    except FileNotFoundError as e:
        logger.error(f"Missing data for batch {batch_id}: {str(e)}")
        return jsonify({'error': 'Required data not found. Please ensure hotspots are labeled.'}), 404
    except ValueError as e:
        logger.error(f"Validation error for batch {batch_id}: {str(e)}")
        return jsonify({'error': 'Invalid input data.'}), 400
    except Exception as e:
        logger.exception(f"Error generating heat loss report for batch {batch_id}: {str(e)}")
        return jsonify({'error': 'Report generation failed'}), 500
