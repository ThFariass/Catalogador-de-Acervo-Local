# No topo do seu arquivo .py
import os
import zipfile
import xml.etree.ElementTree as ET # Para ler o arquivo XML
from qgis.utils import iface
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QListWidget, QMessageBox, QFileDialog
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap # Para manipular a imagem de preview
from qgis.core import QgsRasterLayer, QgsProject, Qgis, QgsMessageLog

class CatalogadorHDF5(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Catalogador de Acervo HDF5 com Preview Local")
        self.setGeometry(200, 100, 700, 850)
        
        self.root_path = None
        self.archive_extension = '.zip'
        self.target_file_extension = '.h5'
        self.preview_image_extension = '.png'
        self.metadata_file_extension = '.xml'

        # --- CONSTRUÇÃO DA INTERFACE (COM UMA PEQUENA ADIÇÃO) ---
        layout = QVBoxLayout()
        # ... (Botões e listas como antes) ...
        self.select_folder_button = QPushButton("Selecionar Pasta Raiz das Imagens")
        self.select_folder_button.clicked.connect(self.select_root_folder)
        layout.addWidget(self.select_folder_button)
        self.path_label = QLabel("Verificando HD externo em E:...")
        self.path_label.setStyleSheet("font-style: italic; color: grey;")
        layout.addWidget(self.path_label)

        self.catalog_label = QLabel("Catálogos (Pastas):")
        layout.addWidget(self.catalog_label)
        self.catalog_list = QListWidget()
        self.catalog_list.itemClicked.connect(self.load_zip_files_from_folder)
        layout.addWidget(self.catalog_list)
        
        self.image_label = QLabel("Arquivos Disponíveis (.zip):")
        layout.addWidget(self.image_label)
        self.image_list = QListWidget()
        self.image_list.itemClicked.connect(self.on_zip_file_selected)
        layout.addWidget(self.image_list)

        # --- VITRINE DE PRÉ-VISUALIZAÇÃO (IMAGEM) ---
        self.preview_label = QLabel("Pré-visualização da imagem aparecerá aqui.")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        self.preview_label.setMinimumHeight(300)
        layout.addWidget(self.preview_label)

        # --- NOVO PAINEL DE METADADOS (TEXTO) ---
        self.metadata_label = QLabel("Metadados do arquivo aparecerão aqui.")
        self.metadata_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.metadata_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc; padding: 5px;")
        self.metadata_label.setWordWrap(True) # Para quebrar linha
        layout.addWidget(self.metadata_label)
        
        # ... (Botões de carregar e sair como antes) ...
        self.show_image_button = QPushButton("Carregar Imagem (.h5) no QGIS")
        self.show_image_button.clicked.connect(self.load_h5_from_zip_into_qgis)
        self.show_image_button.setEnabled(False)
        layout.addWidget(self.show_image_button)
        self.exit_button = QPushButton("Sair")
        self.exit_button.clicked.connect(self.close)
        layout.addWidget(self.exit_button)
        self.setLayout(layout)
        # --- FIM DA CONSTRUÇÃO DA INTERFACE ---

        # Tenta encontrar o drive E: automaticamente
        self.initialize_default_drive()

    def on_zip_file_selected(self):
        """Função chamada quando um .zip é selecionado. Agora é muito mais direta."""
        self.activate_show_button()
        self.preview_label.setText("Lendo arquivo...")
        self.metadata_label.setText("")

        selected_zip_item = self.image_list.currentItem()
        if not selected_zip_item: return

        zip_filename = selected_zip_item.text()
        zip_filepath = os.path.join(self.root_path, self.catalog_list.currentItem().text(), zip_filename)

        self.display_preview_from_local_zip(zip_filepath)

    def display_preview_from_local_zip(self, zip_filepath):
        """
        Versão final que usa a regra de negócio para selecionar o XML correto (contendo 'SLC').
        """
        png_data = None
        metadata_text = "Metadados:\n"
        
        try:
            with zipfile.ZipFile(zip_filepath, 'r') as zf:
                xml_filename_to_process = None
                png_filename_to_process = None
                
                # --- LÓGICA DE BUSCA REFINADA ---
                # 1. Fazemos uma varredura para identificar os arquivos candidatos.
                all_files_in_zip = zf.namelist()
                
                # Busca pelo arquivo PNG (pega o primeiro que encontrar)
                for file in all_files_in_zip:
                    if file.lower().endswith(self.preview_image_extension):
                        png_filename_to_process = file
                        break
                
                # Busca pelo arquivo XML, regra de negócio!
                for file in all_files_in_zip:
                    # A CONDIÇÃO-CHAVE: O nome do arquivo deve conter 'slc' E terminar com .xml
                    if 'slc' in file.lower() and file.lower().endswith(self.metadata_file_extension):
                        xml_filename_to_process = file
                        break # Encontramos o XML correto, não precisamos procurar mais.
                
                # Processa o arquivo de imagem, se encontrado
                if png_filename_to_process:
                    png_data = zf.read(png_filename_to_process)
                
                # Processa o arquivo de metadados, APENAS se o arquivo 'SLC' foi encontrado
                if xml_filename_to_process:
                    xml_content = zf.read(xml_filename_to_process)
                    try:
                        root = ET.fromstring(xml_content)
                        
                        # Seu código de busca, que agora atuará no XML correto
                        coord_first_near = root.find('.//coord_first_near')
                        coord_first_far = root.find('.//coord_first_far')
                        coord_last_near = root.find('.//coord_last_near')
                        coord_last_far = root.find('.//coord_last_far')
                        
                        if coord_first_near is not None and coord_first_near.text:
                            metadata_text += f"- coord_first_near: {coord_first_near.text.strip()}\n"
                        if coord_first_far is not None and coord_first_far.text:
                            metadata_text += f"- coord_first_far: {coord_first_far.text.strip()}\n"
                        if coord_last_near is not None and coord_last_near.text:
                            metadata_text += f"- coord_last_near: {coord_last_near.text.strip()}\n"
                        if coord_last_far is not None and coord_last_far.text:
                            metadata_text += f"- coord_last_far: {coord_last_far.text.strip()}\n"

                    except ET.ParseError:
                        metadata_text += "- Erro ao ler o formato do XML."

        except Exception as e:
            self.preview_label.setText("Erro ao ler o arquivo ZIP.")
            self.metadata_label.setText(f"Erro: {e}")
            return
        
        if len(metadata_text) > 12:
            self.metadata_label.setText(metadata_text)
        else:
            # Mensagem mais específica se o XML correto não for achado
            self.metadata_label.setText("Metadados não exibidos (arquivo XML com 'SLC' não encontrado).")

        if png_data:
            pixmap = QPixmap()
            pixmap.loadFromData(png_data)
            self.preview_label.setPixmap(pixmap.scaled(self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.preview_label.setText("Imagem de preview (.png) não encontrada no ZIP.")


    def initialize_default_drive(self):
        """Tenta encontrar e usar o drive 'E:' como padrão."""
        default_path = "E:\\"
        if os.path.exists(default_path):
            QgsMessageLog.logMessage("Arquiteto informa: Drive E: detectado. Carregando acervo...", 'Catalogador', level=Qgis.Info)
            self.update_root_path(default_path)
        else:
            self.path_label.setText("Drive E: não encontrado. Por favor, selecione a pasta raiz manualmente.")
            self.path_label.setStyleSheet("font-style: italic; color: orange;")

    def select_root_folder(self):
        """Permite que o usuário selecione uma pasta manualmente."""
        path = QFileDialog.getExistingDirectory(self, "Selecione a pasta raiz que contém os catálogos")
        if path:
            self.update_root_path(path)

    def update_root_path(self, path):
        """Função central para atualizar o caminho e recarregar os catálogos."""
        self.root_path = path
        self.path_label.setText(f"Acervo em: {self.root_path}")
        self.path_label.setStyleSheet("font-style: normal; color: black;")
        self.populate_catalogs()

    def populate_catalogs(self):
        """Lê as subpastas da pasta raiz (exatamente como antes)."""
        self.catalog_list.clear()
        self.image_list.clear()
        self.show_image_button.setEnabled(False)
        if not self.root_path: return

        try:
            for item_name in os.listdir(self.root_path):
                if os.path.isdir(os.path.join(self.root_path, item_name)):
                    self.catalog_list.addItem(item_name)
        except OSError as e:
            QMessageBox.critical(self, "Erro de Leitura", f"Erro ao ler diretório: {e}")

    def load_zip_files_from_folder(self):
        """MODIFICADO: Agora procura por arquivos .zip."""
        self.image_list.clear()
        self.show_image_button.setEnabled(False)
        selected_catalog_item = self.catalog_list.currentItem()
        if not selected_catalog_item: return

        catalog_name = selected_catalog_item.text()
        catalog_path = os.path.join(self.root_path, catalog_name)

        try:
            for file_name in os.listdir(catalog_path):
                if file_name.lower().endswith(self.archive_extension):
                    self.image_list.addItem(file_name)
        except OSError as e:
            QMessageBox.critical(self, "Erro de Leitura", f"Erro ao ler pasta do catálogo: {e}")

    def activate_show_button(self):
        if self.image_list.currentItem():
            self.show_image_button.setEnabled(True)

    def load_h5_from_zip_into_qgis(self):
        """
        A GRANDE MUDANÇA: Lógica para ler o .zip e carregar o .h5.
        """
        if not all([self.root_path, self.catalog_list.currentItem(), self.image_list.currentItem()]):
            QMessageBox.warning(self, "Atenção", "Seleção incompleta.")
            return

        catalog_name = self.catalog_list.currentItem().text()
        zip_filename = self.image_list.currentItem().text()
        zip_filepath = os.path.join(self.root_path, catalog_name, zip_filename)

        h5_filename_inside_zip = None
        try:
            # Usamos a biblioteca zipfile para "espiar" dentro do arquivo
            with zipfile.ZipFile(zip_filepath, 'r') as zf:
                # Procuramos por um arquivo que termine com .h5
                for file in zf.namelist():
                    if file.lower().endswith(self.target_file_extension):
                        h5_filename_inside_zip = file
                        break # Encontramos, não precisa procurar mais

        except (zipfile.BadZipFile, FileNotFoundError) as e:
            QMessageBox.critical(self, "Erro de Arquivo", f"Não foi possível ler o arquivo ZIP.\nEle pode estar corrompido ou não foi encontrado.\n\nErro: {e}")
            return
        
        if h5_filename_inside_zip:
            # Construímos o "endereço virtual" que o QGIS entende
            qgis_virtual_path = f"/vsizip/{zip_filepath}/{h5_filename_inside_zip}"
            
            layer_name = os.path.splitext(h5_filename_inside_zip)[0]
            iface.addRasterLayer(qgis_virtual_path, layer_name)
            QgsMessageLog.logMessage(f"Arquiteto informa: Imagem '{qgis_virtual_path}' carregada.", 'Catalogador', level=Qgis.Success)
        else:
            QMessageBox.warning(self, "Item não Encontrado", f"Não foi encontrado nenhum arquivo '{self.target_file_extension}' dentro de:\n{zip_filename}")

minha_ferramenta = CatalogadorHDF5()
minha_ferramenta.show()