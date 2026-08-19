from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Indenter
import pandas as pd

def create_summary_table(json_data, json_path):
    # Extract necessary metadata
    metadata = json_data.get('metadata', {})
    component = metadata.get('component', {})
    
    summary_data = [
        ['Item', 'Details'],
        ['SBOM File', json_path],
        ['SBOM Type', json_data.get('bomFormat', '')],
        ['Version', json_data.get('specVersion', '')],
        ['Name', component.get('name', '')],
        ['Created', metadata.get('timestamp', '')],
        ['Packages', len(json_data.get('components', []))],
        ['Relationships', len(json_data.get('dependencies', []))]
    ]

    # Create table
    table = Table(summary_data, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    return table

def create_supplier_table(json_data):
    metadata = json_data.get('metadata', {})
    supplier = metadata.get('supplier', {})
    
    supplier_data = [
        ['Item', 'Details'],
        ['Name', supplier.get('name', 'N/A')],
        ['Contact', ', '.join([contact.get('name', 'N/A') for contact in supplier.get('contact', [])])],
        ['Email', ', '.join([contact.get('email', 'N/A') for contact in supplier.get('contact', [])])],
        ['URL', ', '.join(supplier.get('url', ['N/A']))]
    ]

    # Create table
    table = Table(supplier_data, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    return table

def create_dependency_paragraphs(json_data):
    dependencies = json_data.get('dependencies', [])
    paragraphs = []

    for dependency in dependencies:
        ref = dependency.get('ref', '')
        depends_on_list = dependency.get('dependsOn', [])
        depends_on = depends_on_list if depends_on_list else ['None']
        
        paragraph = Paragraph(f"<b>Dependency:</b> {ref}<br/><b>Depends On:</b>", getSampleStyleSheet()['Normal'])
        paragraphs.append(paragraph)
        for item in depends_on:
            paragraphs.append(Indenter(left=20))
            paragraphs.append(Paragraph(f"{item}", getSampleStyleSheet()['Normal']))
            paragraphs.append(Indenter(left=-20))
        paragraphs.append(Spacer(1, 12))  # Add some space between paragraphs

    return paragraphs

def create_components_type_summary_table(df):
    # Group by type and count
    type_counts = df['Type'].value_counts().reset_index()
    type_counts.columns = ['Type', 'Count']

    # Convert to list of lists for table
    summary_data = [type_counts.columns.values.tolist()] + type_counts.values.tolist()

    # Create table
    table = Table(summary_data, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    return table

def create_license_summary_table(df):
    # Group by license and count
    license_counts = df['License'].value_counts().reset_index()
    license_counts.columns = ['License', 'Count']

    # Convert to list of lists for table
    summary_data = [license_counts.columns.values.tolist()] + license_counts.values.tolist()

    # Create table
    table = Table(summary_data, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    return table

def dataframe_to_pdf(json_data, df, pdf_path, json_path):
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=landscape(letter),
        leftMargin=40,
        rightMargin=40,
        topMargin=20,
        bottomMargin=20
    )
    elements = []

    # Add SBOM summary
    summary_title = Paragraph('1. SBOM Summary', ParagraphStyle('Title', fontSize=14, spaceAfter=14))
    elements.append(summary_title)
    summary_table = create_summary_table(json_data, json_path)
    elements.append(summary_table)
    elements.append(Spacer(1, 12))

    # Add Supplier Information
    supplier_summary_title = Paragraph('2. Supplier Information', ParagraphStyle('Title', fontSize=14, spaceAfter=14))
    elements.append(supplier_summary_title)
    supplier_table = create_supplier_table(json_data)
    elements.append(supplier_table)
    elements.append(Spacer(1, 12))

    # Add Components summary title
    components_summary_title = Paragraph('3. Components Summary', ParagraphStyle('Title', fontSize=14, spaceAfter=14))
    elements.append(components_summary_title)
    elements.append(Spacer(1, 12))

    # Style for normal text
    style = getSampleStyleSheet()
    normal_style = style['Normal']
    normal_style.fontSize = 8

    # Convert DataFrame to list of lists and ensure all cells are strings
    data = [df.columns.values.tolist()] + [[Paragraph(str(cell), normal_style) for cell in row] for row in df.values.tolist()]

    # Create a table with specific column widths
    col_widths = [250, 100, 100, 200]  # Adjusted widths for better fit in landscape
    table = Table(data, colWidths=col_widths)
    
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),  # Set font size for all table cells
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('WORDWRAP', (0, 0), (-1, -1), 'CJK')
    ]))

    elements.append(table)
    elements.append(Spacer(1, 12))

    # Add Dependency summary title
    dependency_summary_title = Paragraph('4. Dependency Summary', ParagraphStyle('Title', fontSize=14, spaceAfter=14))
    elements.append(dependency_summary_title)
    elements.append(Spacer(1, 12))

    # Add Dependency paragraphs
    dependency_paragraphs = create_dependency_paragraphs(json_data)
    elements.extend(dependency_paragraphs)

    # Add Components Type Summary title
    components_type_summary_title = Paragraph('5. Components Type Summary', ParagraphStyle('Title', fontSize=14, spaceAfter=14))
    elements.append(components_type_summary_title)
    elements.append(Spacer(1, 12))

    # Add Components Type Summary table
    components_type_summary_table = create_components_type_summary_table(df)
    elements.append(components_type_summary_table)
    elements.append(Spacer(1, 12))

    # Add License Summary title
    license_summary_title = Paragraph('6. License Summary', ParagraphStyle('Title', fontSize=14, spaceAfter=14))
    elements.append(license_summary_title)
    elements.append(Spacer(1, 12))

    # Add License Summary table
    license_summary_table = create_license_summary_table(df)
    elements.append(license_summary_table)

    doc.build(elements)