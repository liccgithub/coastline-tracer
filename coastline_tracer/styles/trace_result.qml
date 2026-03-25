<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28" styleCategories="AllStyleCategories">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
    <Private>0</Private>
  </flags>
  <renderer-v2 type="categorizedSymbol" attr="source_layer" enableorderby="0" forceraster="0" symbollevels="0">
    <categories>
      <category symbol="0" label="海岸线" value="coast" render="true"/>
      <category symbol="1" label="建设线" value="build_coast" render="true"/>
      <category symbol="2" label="陆地边界" value="land_border" render="true"/>
      <category symbol="3" label="其他" value="" render="true"/>
    </categories>
    <symbols>
      <symbol name="0" type="line" clip_to_extent="1" alpha="1" force_rhr="0">
        <data_defined_properties>
          <Option type="Map">
            <Option name="name" value="" type="QString"/>
            <Option name="properties"/>
            <Option name="type" value="collection" type="QString"/>
          </Option>
        </data_defined_properties>
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <Option type="Map">
            <Option name="line_color" value="33,150,243,255" type="QString"/>
            <Option name="line_width" value="1" type="QString"/>
            <Option name="line_width_unit" value="MM" type="QString"/>
            <Option name="capstyle" value="round" type="QString"/>
            <Option name="joinstyle" value="round" type="QString"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="1" type="line" clip_to_extent="1" alpha="1" force_rhr="0">
        <data_defined_properties>
          <Option type="Map">
            <Option name="name" value="" type="QString"/>
            <Option name="properties"/>
            <Option name="type" value="collection" type="QString"/>
          </Option>
        </data_defined_properties>
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <Option type="Map">
            <Option name="line_color" value="255,152,0,255" type="QString"/>
            <Option name="line_width" value="0.86" type="QString"/>
            <Option name="line_width_unit" value="MM" type="QString"/>
            <Option name="capstyle" value="round" type="QString"/>
            <Option name="joinstyle" value="round" type="QString"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="2" type="line" clip_to_extent="1" alpha="1" force_rhr="0">
        <data_defined_properties>
          <Option type="Map">
            <Option name="name" value="" type="QString"/>
            <Option name="properties"/>
            <Option name="type" value="collection" type="QString"/>
          </Option>
        </data_defined_properties>
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <Option type="Map">
            <Option name="line_color" value="121,85,72,255" type="QString"/>
            <Option name="line_width" value="0.72" type="QString"/>
            <Option name="line_width_unit" value="MM" type="QString"/>
            <Option name="capstyle" value="round" type="QString"/>
            <Option name="joinstyle" value="round" type="QString"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="3" type="line" clip_to_extent="1" alpha="1" force_rhr="0">
        <data_defined_properties>
          <Option type="Map">
            <Option name="name" value="" type="QString"/>
            <Option name="properties"/>
            <Option name="type" value="collection" type="QString"/>
          </Option>
        </data_defined_properties>
        <layer class="SimpleLine" enabled="1" pass="0" locked="0">
          <Option type="Map">
            <Option name="line_color" value="158,158,158,255" type="QString"/>
            <Option name="line_width" value="0.72" type="QString"/>
            <Option name="line_width_unit" value="MM" type="QString"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
    <rotation/>
    <sizescale/>
  </renderer-v2>
  <labeling type="simple">
    <settings calloutType="simple">
      <text-style textColor="0,0,0,255" fieldName="source_layer" fontFamily="微软雅黑" fontSize="8"/>
    </settings>
  </labeling>
</qgis>
