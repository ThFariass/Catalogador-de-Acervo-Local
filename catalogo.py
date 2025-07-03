# Imports necessários no topo
import os
import zipfile
import xml.etree.ElementTree as ET
from qgis.utils import iface
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QListWidget, QMessageBox, QFileDialog
from PyQt5.QtCore import Qt, QVariant
from PyQt5.QtGui import QPixmap
from qgis.core import (QgsVectorLayer, QgsVectorDataProvider, QgsField,
                     QgsFeature, QgsGeometry, QgsPointXY, QgsProject,
                     Qgis, QgsMessageLog)

class SentinelaDeAcervo(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sentinela de Acervo (v4.0 - Unificado)")
        self.setGeometry(200, 100, 700, 900)

        # Declaração de todas as "peças" e "memória" do nosso edifício
        self.root_path = None
        self.footprint_layer = None
        self.current_selected_zip_path = None 

        self.archive_extension = '.zip'
        self.target_file_extension = '.tif' 
        self.preview_image_extension = '.png'
        self.metadata_file_extension = '.xml'

        # Construção completa e correta da interface
        layout = QVBoxLayout()

        self.map_button = QPushButton("Mapear Acervo no QGIS")
        self.map_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.map_button.clicked.connect(self.create_footprint_layer)
        layout.addWidget(self.map_button)

        self.select_folder_button = QPushButton("Selecionar Pasta Raiz do Acervo")
        self.select_folder_button.clicked.connect(self.select_root_folder)
        layout.addWidget(self.select_folder_button)

        self.path_label = QLabel("Nenhuma pasta selecionada.")
        layout.addWidget(self.path_label)

        self.catalog_label = QLabel("Catálogos (Via Navegador de Pastas):")
        layout.addWidget(self.catalog_label)
        self.catalog_list = QListWidget()
        self.catalog_list.itemClicked.connect(self.load_zip_files_from_folder)
        layout.addWidget(self.catalog_list)

        self.image_label = QLabel("Imagens Disponíveis (Arquivos):")
        layout.addWidget(self.image_label)
        self.image_list = QListWidget()
        self.image_list.itemClicked.connect(self.on_list_item_selected)
        layout.addWidget(self.image_list)

        self.preview_label = QLabel("Selecione um polígono no mapa ou um item na lista.")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        self.preview_label.setMinimumHeight(300)
        layout.addWidget(self.preview_label)

        self.metadata_label = QLabel("Os metadados aparecerão aqui.")
        self.metadata_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.metadata_label.setWordWrap(True)
        layout.addWidget(self.metadata_label)

        self.load_image_button = QPushButton(f"Carregar Imagem ({self.target_file_extension}) no QGIS")
        self.load_image_button.clicked.connect(self.load_raster_from_zip_into_qgis)
        self.load_image_button.setEnabled(False)
        layout.addWidget(self.load_image_button)

        self.exit_button = QPushButton("Sair")
        self.exit_button.setStyleSheet("background-color: #ff0000   ; color: white; font-weight: bold;")
        self.exit_button.clicked.connect(self.close)
        layout.addWidget(self.exit_button)

        self.setLayout(layout)
        self.initialize_default_drive()

    def create_footprint_layer(self):
        if not self.root_path:
            QMessageBox.warning(self, "Atenção", "Por favor, selecione primeiro a pasta raiz do acervo.")
            return

        layer_name = "Índice do Acervo"
        layers = QgsProject.instance().mapLayersByName(layer_name)
        if layers:
            QgsProject.instance().removeMapLayer(layers[0].id())

        vl = QgsVectorLayer("Polygon?crs=EPSG:4326", layer_name, "memory")
        pr = vl.dataProvider()

        # Definição final e correta dos campos/colunas
        pr.addAttributes([
            QgsField("zip_path", QVariant.String),
            QgsField("product_type", QVariant.String),
            QgsField("satellite_name", QVariant.String),
            QgsField("acquisition_mode", QVariant.String),
            QgsField("look_side", QVariant.String),
            QgsField("satellite_look_angle", QVariant.Double),
            QgsField("acquisition_start_utc", QVariant.String),
            QgsField("orbit_direction", QVariant.String),
            QgsField("polarization", QVariant.String),
            QgsField("product_file", QVariant.String),
            QgsField("range_resolution_near", QVariant.Double),
            QgsField("range_resolution_center", QVariant.Double),
            QgsField("range_resolution", QVariant.Double),
            QgsField("product_level", QVariant.String),
            QgsField("acquisiton_mode", QVariant.String),
            QgsField("azimuth_resolution", QVariant.Double),
            QgsField("incidence_near", QVariant.Double),
            QgsField("incidence_center", QVariant.Double),
            QgsField("incidence_far", QVariant.Double),
            QgsField("acquisition_id", QVariant.Double)
        ])
        vl.updateFields()

        QgsMessageLog.logMessage("Iniciando mapeamento do acervo...", 'Sentinela', Qgis.Info)
        features = []
        for catalog_name in os.listdir(self.root_path):
            try:
                catalog_path = os.path.join(self.root_path, catalog_name)
                if not os.path.isdir(catalog_path): continue

                for zip_filename in os.listdir(catalog_path):
                    if not zip_filename.lower().endswith(self.archive_extension): continue
                    
                    zip_filepath = os.path.join(catalog_path, zip_filename)
                    extracted_data = self.get_info_from_zip(zip_filepath)
                    
                    if extracted_data:
                        coords = extracted_data['coords']
                        attributes = extracted_data['attributes']
                        
                        points = [
                            QgsPointXY(coords['first_near'][1], coords['first_near'][0]),
                            QgsPointXY(coords['last_near'][1], coords['last_near'][0]),
                            QgsPointXY(coords['last_far'][1], coords['last_far'][0]),
                            QgsPointXY(coords['first_far'][1], coords['first_far'][0])
                        ]
                        
                        feature = QgsFeature()
                        feature.setGeometry(QgsGeometry.fromPolygonXY([points]))
                        
                        # Preenchendo os atributos na ordem correta
                        feature.setAttributes([
                            zip_filepath,
                            attributes['product_type'],
                            attributes['satellite_name'],
                            attributes['acquisition_mode'],
                            attributes['look_side'],
                            attributes['satellite_look_angle'],
                            attributes['acquisition_start_utc'],
                            attributes['orbit_direction'],
                            attributes['polarization'],
                            attributes['product_file'],
                            attributes['range_resolution_near'],
                            attributes['range_resolution_center'],
                            attributes['range_resolution_far'],
                            attributes['product_level'],
                            attributes['acquisition_mode'],
                            attributes['azimuth_resolution'],
                            attributes['incidence_near'],
                            attributes['incidence_center'],
                            attributes['incidence_far'],
                            attributes['acquisition_id']
                        ])
                        features.append(feature)

            except PermissionError:
                QgsMessageLog.logMessage(f"Acesso negado à pasta do sistema '{catalog_name}'. Ignorando.", 'Sentinela', Qgis.Warning)
                continue
        
        pr.addFeatures(features)
        vl.updateExtents()
        QgsProject.instance().addMapLayer(vl)
        self.footprint_layer = vl
        QgsMessageLog.logMessage(f"{len(features)} imagens mapeadas com sucesso!", 'Sentinela', Qgis.Success)

        if self.footprint_layer:
            try: self.footprint_layer.selectionChanged.disconnect(self.on_map_selection_changed)
            except TypeError: pass
            self.footprint_layer.selectionChanged.connect(self.on_map_selection_changed)


    def get_info_from_zip(self, zip_filepath):
        try:
            with zipfile.ZipFile(zip_filepath, 'r') as zf:
                xml_filename = next((f for f in zf.namelist() if 'slc' in f.lower() and f.lower().endswith(self.metadata_file_extension)), None)
                
                if not xml_filename:
                    QgsMessageLog.logMessage(f"Nenhum XML com 'slc' encontrado em {os.path.basename(zip_filepath)}", 'Sentinela', Qgis.Warning)
                    return None

                xml_content = zf.read(xml_filename)
                root = ET.fromstring(xml_content)
                
                namespace = {}
                if '}' in root.tag:
                    namespace = {'ns': root.tag.split('}')[0][1:]}

                def find_text_safely(path):
                    if namespace: path = path.replace('.//', './/ns:')
                    node = root.find(path, namespace)
                    return node.text.strip() if node is not None and node.text else None

                # Extrai as Coordenadas
                def parse_coord(node_name):
                    text_value = find_text_safely(f".//{node_name}")
                    if text_value:
                        parts = text_value.split()
                        return float(parts[-2]), float(parts[-1])
                    return None
                
                coords = {'first_near': parse_coord('coord_first_near'), 'first_far': parse_coord('coord_first_far'),
                        'last_near': parse_coord('coord_last_near'), 'last_far': parse_coord('coord_last_far')}
                
                # Extrai os Atributos usando as tags corretas
                attributes = {
                    'product_type': find_text_safely('.//product_type') or 'N/D',
                    'satellite_name': find_text_safely('.//satellite_name') or 'N/D',
                    'acquisition_mode': find_text_safely('.//acquisition_mode') or 'N/D',
                    'look_side': find_text_safely('.//look_side') or 'N/D',
                    'acquisition_start_utc': find_text_safely('.//acquisition_start_utc') or 'N/D', # Tratado como texto
                    'orbit_direction': find_text_safely('.//orbit_direction') or 'N/D',
                    'polarization': find_text_safely('.//polarization') or 'N/D',
                    'product_file': find_text_safely('.//product_file') or 'N/D',
                    'product_level': find_text_safely('.//product_level') or 'N/D',
                    'acquisition_mode': find_text_safely('.//acquisition_mode') or 'N/D'
                }
                try:
                    attributes['satellite_look_angle'] = float(find_text_safely('.//satellite_look_angle') or 0.0)
                    attributes['range_resolution_near'] = float(find_text_safely('.//range_resolution_near') or 0.0)
                    attributes['range_resolution_center'] = float(find_text_safely('.//range_resolution_center') or 0.0)
                    attributes['range_resolution_far'] = float(find_text_safely('.//range_resolution_far') or 0.0)
                    attributes['azimuth_resolution'] = float(find_text_safely('.//azimuth_resolution') or 0.0)
                    attributes['incidence_near'] = float(find_text_safely('.//incidence_near') or 0.0)
                    attributes['incidence_center'] = float(find_text_safely('.//incidence_center') or 0.0)
                    attributes['incidence_far'] = float(find_text_safely('.//incidence_far') or 0.0)
                    attributes['acquisition_id'] = float(find_text_safely('.//acquisition_id') or 0.0)
                except (ValueError, TypeError):
                    attributes['satellite_look_angle'] = 0.0
                    attributes['range_resolution_near'] = 0.0
                    attributes['range_resolution_center'] = 0.0
                    attributes['range_resolution_far'] = 0.0
                    attributes['azimuth_resolution'] = 0.0
                    attributes['incidence_near'] = 0.0
                
                if all(coords.values()):
                    return {'coords': coords, 'attributes': attributes}

        except Exception as e:
            QgsMessageLog.logMessage(f"ERRO CRÍTICO ao processar {os.path.basename(zip_filepath)}: {e}", 'Sentinela', Qgis.Critical)
        
        return None

    def on_map_selection_changed(self):
        if not self.footprint_layer: return
        selected_features = self.footprint_layer.selectedFeatures()
        if selected_features:
            feature = selected_features[0]
            zip_filepath = feature['zip_path']
            self.show()
            self.update_selection_and_preview(zip_filepath)
        else:
            self.clear_selection_and_preview()

    def on_list_item_selected(self):
        selected_zip_item = self.image_list.currentItem()
        if not selected_zip_item: return
        zip_filename = selected_zip_item.text()
        zip_filepath = os.path.join(self.root_path, self.catalog_list.currentItem().text(), zip_filename)
        self.update_selection_and_preview(zip_filepath)

    def update_selection_and_preview(self, zip_filepath):
        self.current_selected_zip_path = zip_filepath
        self.load_image_button.setEnabled(True)
        self.display_preview_from_local_zip(zip_filepath)

    def clear_selection_and_preview(self):
        self.current_selected_zip_path = None
        self.load_image_button.setEnabled(False)
        self.preview_label.setText("Selecione um polígono no mapa ou um item na lista.")
        self.metadata_label.setText("Os metadados aparecerão aqui.")
        self.preview_label.clear()

    def load_raster_from_zip_into_qgis(self):
        if not self.current_selected_zip_path:
            QMessageBox.warning(self, "Atenção", "Nenhum arquivo selecionado.")
            return
        
        zip_filepath = self.current_selected_zip_path
        target_filename_inside_zip = None
        try:
            with zipfile.ZipFile(zip_filepath, 'r') as zf:
                # Loop para encontrar o arquivo .tif específico
                for file in zf.namelist():
                    # Verifica se o nome do arquivo contém 'grd' E termina com .tif
                    if 'grd' in file.lower() and file.lower().endswith(self.target_file_extension):
                        target_filename_inside_zip = file
                        break
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível ler o arquivo ZIP: {e}")
            return
        
        if target_filename_inside_zip:
            qgis_virtual_path = f"/vsizip/{zip_filepath}/{target_filename_inside_zip}"
            layer_name = os.path.splitext(os.path.basename(target_filename_inside_zip))[0]
            iface.addRasterLayer(qgis_virtual_path, layer_name)
            QgsMessageLog.logMessage(f"Imagem GRD '{target_filename_inside_zip}' carregada com sucesso.", 'Sentinela', Qgis.Success)
        else:
            QMessageBox.warning(self, "Não Encontrado", f"Nenhum arquivo {self.target_file_extension} encontrado dentro do ZIP.")

    def display_preview_from_local_zip(self, zip_filepath):
        png_data = None
        metadata_text = "Metadados:\n"
        try:
            with zipfile.ZipFile(zip_filepath, 'r') as zf:
                xml_filename_to_process, png_filename_to_process = None, None
                for file in zf.namelist():
                    if png_filename_to_process is None and file.lower().endswith(self.preview_image_extension):
                        png_filename_to_process = file
                    if xml_filename_to_process is None and 'slc' in file.lower() and file.lower().endswith(self.metadata_file_extension):
                        xml_filename_to_process = file
                    if png_filename_to_process and xml_filename_to_process:
                        break
                
                if png_filename_to_process:
                    png_data = zf.read(png_filename_to_process)
                # if xml_filename_to_process:
                #     xml_content = zf.read(xml_filename_to_process)
                #     root = ET.fromstring(xml_content)
                #     coord_first_near = root.find('.//coord_first_near')
                #     if coord_first_near is not None and coord_first_near.text:
                #          metadata_text += f"- coord_first_near: {coord_first_near.text.strip()}\n"
                    # Adicione aqui as outras coordenadas se desejar
        except Exception as e:
            print(f"Erro no display_preview: {e}")

        self.metadata_label.setText(metadata_text)
        if png_data:
            pixmap = QPixmap()
            pixmap.loadFromData(png_data)
            self.preview_label.setPixmap(pixmap.scaled(self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.preview_label.setText("Imagem de preview (.png) não encontrada no ZIP.")

    def initialize_default_drive(self):
        default_path = "E:\\"
        if os.path.exists(default_path):
            self.update_root_path(default_path)
        else:
            self.path_label.setText("Drive E: não encontrado. Selecione a pasta raiz manualmente.")

    def select_root_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Selecione a pasta raiz dos catálogos")
        if path:
            self.update_root_path(path)

    def update_root_path(self, path):
        self.root_path = path
        self.path_label.setText(f"Acervo em: {self.root_path}")
        self.populate_catalogs()

    def populate_catalogs(self):
        self.catalog_list.clear()
        if not self.root_path: return
        try:
            for item_name in os.listdir(self.root_path):
                if os.path.isdir(os.path.join(self.root_path, item_name)):
                    self.catalog_list.addItem(item_name)
        except OSError as e:
            QMessageBox.critical(self, "Erro", f"Erro ao ler diretório: {e}")

    def load_zip_files_from_folder(self):
        self.image_list.clear()
        selected_catalog_item = self.catalog_list.currentItem()
        if not selected_catalog_item: return
        catalog_name = selected_catalog_item.text()
        catalog_path = os.path.join(self.root_path, catalog_name)
        try:
            for file_name in os.listdir(catalog_path):
                if file_name.lower().endswith(self.archive_extension):
                    self.image_list.addItem(file_name)
        except OSError as e:
            QMessageBox.critical(self, "Erro", f"Erro ao ler pasta: {e}")

# Esta linha cria uma instância do nosso plicativo e o exibe.
minha_ferramenta = SentinelaDeAcervo()
minha_ferramenta.show()