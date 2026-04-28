import {
  AppstoreOutlined,
  BuildOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
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
import MaterialBatchDetailPage from './pages/MaterialBatchDetailPage'
import MaterialBatchesPage from './pages/MaterialBatchesPage'
import MaterialChunkPage from './pages/MaterialChunkPage'
import MaterialParsePage from './pages/MaterialParsePage'
import ModelDefaultsPage from './pages/ModelDefaultsPage'
import ModelsPage from './pages/ModelsPage'
import ParserStrategiesPage from './pages/ParserStrategiesPage'
import ParseRunDetailPage from './pages/ParseRunDetailPage'
import ParseRunsPage from './pages/ParseRunsPage'
import ProcessingRulesPage from './pages/ProcessingRulesPage'

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
  ]

  return (
    <div className="workspace">
      <aside className="configRail">
        <div className="railSectionTitle">配置中心</div>
        <Menu
          className="configMenu"
          mode="inline"
          selectedKeys={[selectedKey]}
          defaultOpenKeys={['agent-root', 'material-root']}
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
        </Routes>
      </section>
    </div>
  )
}

function BuildWorkspace() {
  const location = useLocation()
  const selectedKey = location.pathname.includes('/chunk-compare')
    ? '/build/chunk-compare'
    : location.pathname.includes('/chunk-runs')
      ? '/build/chunk-runs'
      : location.pathname.includes('/material-chunk')
        ? '/build/material-chunk'
        : location.pathname.includes('/parse-runs')
          ? '/build/parse-runs'
          : '/build/material-parse'
  const items: MenuProps['items'] = [
    { key: '/build/material-parse', icon: <FileTextOutlined />, label: <Link to="/build/material-parse">材料解析</Link> },
    { key: '/build/parse-runs', icon: <BuildOutlined />, label: <Link to="/build/parse-runs">解析任务</Link> },
    { key: '/build/material-chunk', icon: <FileTextOutlined />, label: <Link to="/build/material-chunk">材料分块</Link> },
    { key: '/build/chunk-runs', icon: <BuildOutlined />, label: <Link to="/build/chunk-runs">分块任务</Link> },
    { key: '/build/chunk-compare', icon: <DatabaseOutlined />, label: <Link to="/build/chunk-compare">分块对比</Link> },
  ]

  return (
    <div className="workspace">
      <aside className="configRail">
        <div className="railSectionTitle">材料处理</div>
        <Menu className="configMenu" mode="inline" selectedKeys={[selectedKey]} items={items} />
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
        </Routes>
      </section>
    </div>
  )
}

function SettingsPage() {
  const location = useLocation()
  const selectedKey = location.pathname.includes('/processing-rules')
    ? '/settings/processing-rules'
    : '/settings/model-defaults'
  const items: MenuProps['items'] = [
    { key: '/settings/model-defaults', icon: <SettingOutlined />, label: <Link to="/settings/model-defaults">默认模型</Link> },
    { key: '/settings/processing-rules', icon: <FileTextOutlined />, label: <Link to="/settings/processing-rules">默认处理规则</Link> },
  ]

  return (
    <div className="workspace">
      <aside className="configRail">
        <div className="railSectionTitle">设置</div>
        <Menu className="configMenu" mode="inline" selectedKeys={[selectedKey]} items={items} />
      </aside>
      <section className="workspaceContent">
        <Routes>
          <Route index element={<Navigate to="/settings/model-defaults" replace />} />
          <Route path="model-defaults" element={<ModelDefaultsPage />} />
          <Route path="processing-rules" element={<ProcessingRulesPage />} />
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
