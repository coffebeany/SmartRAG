import {
  AppstoreOutlined,
  BuildOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  FundProjectionScreenOutlined,
  NodeIndexOutlined,
  RobotOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { Layout, Menu, Typography } from 'antd'
import type { MenuProps } from 'antd'
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import AgentProfilesPage from './pages/AgentProfilesPage'
import ChunkComparePage from './pages/ChunkComparePage'
import ChunkRunDetailPage from './pages/ChunkRunDetailPage'
import ChunkRunsPage from './pages/ChunkRunsPage'
import ChunkStrategiesPage from './pages/ChunkStrategiesPage'
import ComponentConfigsPage from './pages/ComponentConfigsPage'
import EvaluationDatasetDetailPage from './pages/EvaluationDatasetDetailPage'
import EvaluationDatasetRunsPage from './pages/EvaluationDatasetRunsPage'
import EvaluationDatasetsPage from './pages/EvaluationDatasetsPage'
import EvaluationReportDetailPage from './pages/EvaluationReportDetailPage'
import EvaluationReportsPage from './pages/EvaluationReportsPage'
import MaterialBatchDetailPage from './pages/MaterialBatchDetailPage'
import MaterialBatchesPage from './pages/MaterialBatchesPage'
import MaterialChunkPage from './pages/MaterialChunkPage'
import MaterialParsePage from './pages/MaterialParsePage'
import MaterialVectorPage from './pages/MaterialVectorPage'
import ModelDefaultsPage from './pages/ModelDefaultsPage'
import ModelsPage from './pages/ModelsPage'
import ParserStrategiesPage from './pages/ParserStrategiesPage'
import ParseRunDetailPage from './pages/ParseRunDetailPage'
import ParseRunsPage from './pages/ParseRunsPage'
import ProcessingRulesPage from './pages/ProcessingRulesPage'
import RagFlowBuilderPage from './pages/RagFlowBuilderPage'
import RagFlowExperiencePage from './pages/RagFlowExperiencePage'
import RagFlowsPage from './pages/RagFlowsPage'
import VectorDBsPage from './pages/VectorDBsPage'
import VectorRunDetailPage from './pages/VectorRunDetailPage'
import VectorRunsPage from './pages/VectorRunsPage'

const { Header, Content } = Layout

function getTopKey(pathname: string) {
  if (pathname.startsWith('/build')) return 'build'
  if (pathname.startsWith('/settings')) return 'settings'
  return 'config'
}

function ConfigWorkspace() {
  const location = useLocation()
  const selectedKey = location.pathname.includes('/embedding')
    ? '/config/embedding'
    : location.pathname.includes('/vectorization/vectordbs')
      ? '/config/vectorization/vectordbs'
      : location.pathname.includes('/materials/rules')
        ? '/config/materials/rules'
        : location.pathname.includes('/materials/chunkers')
          ? '/config/materials/chunkers'
          : location.pathname.includes('/materials/parsers')
            ? '/config/materials/parsers'
            : location.pathname.includes('/materials')
              ? '/config/materials/batches'
              : location.pathname.includes('/agent')
                ? '/config/agent'
                : '/config/llm'

  const items: MenuProps['items'] = [
    {
      key: 'agent-root',
      icon: <RobotOutlined />,
      label: 'Agent管理',
      children: [
        { key: '/config/llm', icon: <AppstoreOutlined />, label: <Link to="/config/llm">LLM管理</Link> },
        { key: '/config/embedding', icon: <DatabaseOutlined />, label: <Link to="/config/embedding">Embedded管理</Link> },
        { key: '/config/agent', icon: <RobotOutlined />, label: <Link to="/config/agent">Agent管理</Link> },
      ],
    },
    {
      key: 'material-root',
      icon: <FolderOpenOutlined />,
      label: '材料管理',
      children: [
        { key: '/config/materials/batches', icon: <FolderOpenOutlined />, label: <Link to="/config/materials/batches">批次管理</Link> },
        { key: '/config/materials/parsers', icon: <FileTextOutlined />, label: <Link to="/config/materials/parsers">解析工具</Link> },
        { key: '/config/materials/chunkers', icon: <BuildOutlined />, label: <Link to="/config/materials/chunkers">分块工具</Link> },
      ],
    },
    {
      key: 'vector-root',
      icon: <DatabaseOutlined />,
      label: '向量化',
      children: [
        { key: '/config/vectorization/vectordbs', icon: <DatabaseOutlined />, label: <Link to="/config/vectorization/vectordbs">VectorDB</Link> },
      ],
    },
  ]

  return (
    <div className="workspace">
      <aside className="configRail">
        <div className="railSectionTitle">配置中心</div>
        <Menu
          className="configMenu"
          mode="inline"
          selectedKeys={[selectedKey]}
          defaultOpenKeys={['agent-root', 'material-root', 'vector-root']}
          items={items}
        />
      </aside>
      <section className="workspaceContent">
        <Routes>
          <Route index element={<Navigate to="/config/llm" replace />} />
          <Route
            path="llm"
            element={
              <ModelsPage
                title="LLM管理"
                description="管理用于生成、推理、评测和 Agent dry-run 的大语言模型连接。"
                categoryFilter="llm"
              />
            }
          />
          <Route
            path="embedding"
            element={
              <ModelsPage
                title="Embedded管理"
                description="管理文本向量模型连接，记录维度、批量能力和可用状态。"
                categoryFilter="embedding"
              />
            }
          />
          <Route path="agent" element={<AgentProfilesPage />} />
          <Route path="materials" element={<Navigate to="/config/materials/batches" replace />} />
          <Route path="materials/batches" element={<MaterialBatchesPage />} />
          <Route path="materials/batches/:batchId" element={<MaterialBatchDetailPage />} />
          <Route path="materials/rules" element={<Navigate to="/settings/processing-rules" replace />} />
          <Route path="materials/parsers" element={<ParserStrategiesPage />} />
          <Route path="materials/chunkers" element={<ChunkStrategiesPage />} />
          <Route path="vectorization" element={<Navigate to="/config/vectorization/vectordbs" replace />} />
          <Route path="vectorization/vectordbs" element={<VectorDBsPage />} />
        </Routes>
      </section>
    </div>
  )
}

function BuildWorkspace() {
  const location = useLocation()
  let selectedKey = '/build/material-parse'
  if (location.pathname.includes('/parse-runs')) selectedKey = '/build/parse-runs'
  if (location.pathname.includes('/material-chunk')) selectedKey = '/build/material-chunk'
  if (location.pathname.includes('/chunk-runs')) selectedKey = '/build/chunk-runs'
  if (location.pathname.includes('/material-vector')) selectedKey = '/build/material-vector'
  if (location.pathname.includes('/vector-runs')) selectedKey = '/build/vector-runs'
  if (location.pathname.includes('/rag-flow-builder')) selectedKey = '/build/rag-flow-builder'
  if (location.pathname.includes('/rag-flows')) selectedKey = '/build/rag-flows'
  if (location.pathname.includes('/rag-experience')) selectedKey = '/build/rag-experience'
  if (location.pathname.includes('/evaluation-datasets')) selectedKey = '/build/evaluation-datasets'
  if (location.pathname.includes('/evaluation-datasets/') || location.pathname.includes('/evaluation-dataset-runs')) {
    selectedKey = '/build/evaluation-dataset-runs'
  }
  if (location.pathname.includes('/evaluation-reports')) selectedKey = '/build/evaluation-reports'
  if (location.pathname.includes('/chunk-compare')) selectedKey = '/build/chunk-compare'
  const items: MenuProps['items'] = [
    {
      key: 'build-material-root',
      icon: <FolderOpenOutlined />,
      label: '材料处理',
      children: [
        { key: '/build/material-parse', icon: <FileTextOutlined />, label: <Link to="/build/material-parse">材料解析</Link> },
        { key: '/build/parse-runs', icon: <BuildOutlined />, label: <Link to="/build/parse-runs">解析任务</Link> },
        { key: '/build/material-chunk', icon: <FileTextOutlined />, label: <Link to="/build/material-chunk">材料分块</Link> },
        { key: '/build/chunk-runs', icon: <BuildOutlined />, label: <Link to="/build/chunk-runs">分块任务</Link> },
        { key: '/build/chunk-compare', icon: <DatabaseOutlined />, label: <Link to="/build/chunk-compare">分块对比</Link> },
      ],
    },
    {
      key: 'build-vector-root',
      icon: <DatabaseOutlined />,
      label: '向量化',
      children: [
        { key: '/build/material-vector', icon: <DatabaseOutlined />, label: <Link to="/build/material-vector">材料向量化</Link> },
        { key: '/build/vector-runs', icon: <BuildOutlined />, label: <Link to="/build/vector-runs">向量化任务</Link> },
      ],
    },
    {
      key: 'build-rag-root',
      icon: <NodeIndexOutlined />,
      label: 'RAG 流程',
      children: [
        { key: '/build/rag-flow-builder', icon: <NodeIndexOutlined />, label: <Link to="/build/rag-flow-builder">流程构建</Link> },
        { key: '/build/rag-flows', icon: <NodeIndexOutlined />, label: <Link to="/build/rag-flows">流程列表</Link> },
        { key: '/build/rag-experience', icon: <RobotOutlined />, label: <Link to="/build/rag-experience">流程体验</Link> },
      ],
    },
    {
      key: 'build-eval-root',
      icon: <FundProjectionScreenOutlined />,
      label: '测评',
      children: [
        { key: '/build/evaluation-datasets', icon: <FundProjectionScreenOutlined />, label: <Link to="/build/evaluation-datasets">测评集生成</Link> },
        { key: '/build/evaluation-dataset-runs', icon: <FundProjectionScreenOutlined />, label: <Link to="/build/evaluation-dataset-runs">测评集任务</Link> },
        { key: '/build/evaluation-reports', icon: <FundProjectionScreenOutlined />, label: <Link to="/build/evaluation-reports">应用测评</Link> },
      ],
    },
  ]

  return (
    <div className="workspace">
      <aside className="configRail">
        <div className="railSectionTitle">构建中心</div>
        <Menu
          className="configMenu"
          mode="inline"
          selectedKeys={[selectedKey]}
          defaultOpenKeys={['build-material-root', 'build-vector-root', 'build-rag-root', 'build-eval-root']}
          items={items}
        />
      </aside>
      <section className="workspaceContent">
        <Routes>
          <Route index element={<Navigate to="/build/material-parse" replace />} />
          <Route path="material-parse" element={<MaterialParsePage />} />
          <Route path="parse-runs" element={<ParseRunsPage />} />
          <Route path="parse-runs/:runId" element={<ParseRunDetailPage />} />
          <Route path="material-chunk" element={<MaterialChunkPage />} />
          <Route path="chunk-runs" element={<ChunkRunsPage />} />
          <Route path="chunk-runs/:runId" element={<ChunkRunDetailPage />} />
          <Route path="chunk-compare" element={<ChunkComparePage />} />
          <Route path="material-vector" element={<MaterialVectorPage />} />
          <Route path="vector-runs" element={<VectorRunsPage />} />
          <Route path="vector-runs/:runId" element={<VectorRunDetailPage />} />
          <Route path="rag-flow-builder" element={<RagFlowBuilderPage />} />
          <Route path="rag-flow-builder/:flowId" element={<RagFlowBuilderPage />} />
          <Route path="rag-flows" element={<RagFlowsPage />} />
          <Route path="rag-experience" element={<RagFlowExperiencePage />} />
          <Route path="evaluation-datasets" element={<EvaluationDatasetsPage />} />
          <Route path="evaluation-datasets/:runId" element={<EvaluationDatasetDetailPage />} />
          <Route path="evaluation-dataset-runs" element={<EvaluationDatasetRunsPage />} />
          <Route path="evaluation-dataset-runs/:runId" element={<EvaluationDatasetDetailPage />} />
          <Route path="evaluation-reports" element={<EvaluationReportsPage />} />
          <Route path="evaluation-reports/:runId" element={<EvaluationReportDetailPage />} />
        </Routes>
      </section>
    </div>
  )
}

function SettingsPage() {
  const location = useLocation()
  const selectedKey = location.pathname.includes('/processing-rules')
    ? '/settings/processing-rules'
    : location.pathname.includes('/components/rerank')
      ? '/settings/components/rerank'
      : location.pathname.includes('/components/filter')
        ? '/settings/components/filter'
        : location.pathname.includes('/components/compressor')
          ? '/settings/components/compressor'
          : '/settings/model-defaults'
  const items: MenuProps['items'] = [
    { key: '/settings/model-defaults', icon: <SettingOutlined />, label: <Link to="/settings/model-defaults">默认模型</Link> },
    { key: '/settings/processing-rules', icon: <FileTextOutlined />, label: <Link to="/settings/processing-rules">默认处理规则</Link> },
    {
      key: 'component-root',
      icon: <NodeIndexOutlined />,
      label: '组件配置',
      children: [
        { key: '/settings/components/rerank', icon: <NodeIndexOutlined />, label: <Link to="/settings/components/rerank">Reranker 配置</Link> },
        { key: '/settings/components/filter', icon: <NodeIndexOutlined />, label: <Link to="/settings/components/filter">Filter 配置</Link> },
        { key: '/settings/components/compressor', icon: <NodeIndexOutlined />, label: <Link to="/settings/components/compressor">Compressor 配置</Link> },
      ],
    },
  ]

  return (
    <div className="workspace">
      <aside className="configRail">
        <div className="railSectionTitle">设置</div>
        <Menu
          className="configMenu"
          mode="inline"
          selectedKeys={[selectedKey]}
          defaultOpenKeys={['component-root']}
          items={items}
        />
      </aside>
      <section className="workspaceContent">
        <Routes>
          <Route index element={<Navigate to="/settings/model-defaults" replace />} />
          <Route path="model-defaults" element={<ModelDefaultsPage />} />
          <Route path="processing-rules" element={<ProcessingRulesPage />} />
          <Route path="components/rerank" element={<ComponentConfigsPage nodeType="passage_reranker" />} />
          <Route path="components/filter" element={<ComponentConfigsPage nodeType="passage_filter" />} />
          <Route path="components/compressor" element={<ComponentConfigsPage nodeType="passage_compressor" />} />
        </Routes>
      </section>
    </div>
  )
}

function BottomNav() {
  const location = useLocation()
  const activeKey = getTopKey(location.pathname)
  const items = [
    { key: 'config', icon: <AppstoreOutlined />, label: '配置', to: '/config' },
    { key: 'build', icon: <BuildOutlined />, label: '构建', to: '/build' },
    { key: 'settings', icon: <SettingOutlined />, label: '设置', to: '/settings' },
  ]

  return (
    <nav className="bottomNav" aria-label="Primary">
      {items.map((item) => (
        <Link key={item.key} to={item.to} className={`bottomNavItem ${activeKey === item.key ? 'active' : ''}`}>
          <span className="bottomNavIcon">{item.icon}</span>
          <span>{item.label}</span>
        </Link>
      ))}
    </nav>
  )
}

function Shell() {
  return (
    <Layout className="appShell">
      <Header className="topbar">
        <div>
          <Typography.Title level={4}>SmartRAG</Typography.Title>
          <Typography.Text type="secondary">Less structure, more intelligence.</Typography.Text>
        </div>
      </Header>
      <Content className="content">
        <Routes>
          <Route path="/" element={<Navigate to="/config" replace />} />
          <Route path="/config/*" element={<ConfigWorkspace />} />
          <Route path="/build/*" element={<BuildWorkspace />} />
          <Route path="/settings/*" element={<SettingsPage />} />
          <Route path="/models" element={<Navigate to="/config/llm" replace />} />
          <Route path="/agents" element={<Navigate to="/config/agent" replace />} />
          <Route path="/defaults" element={<Navigate to="/settings/model-defaults" replace />} />
        </Routes>
      </Content>
      <BottomNav />
    </Layout>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  )
}
