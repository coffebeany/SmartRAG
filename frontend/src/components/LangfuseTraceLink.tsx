import { LinkOutlined } from '@ant-design/icons'
import { Button, Tooltip } from 'antd'
import { useLangfuseConfig } from '../api/hooks'

interface LangfuseTraceLinkProps {
  traceId?: string | null
  size?: 'small' | 'middle' | 'large'
}

export default function LangfuseTraceLink({ traceId, size = 'small' }: LangfuseTraceLinkProps) {
  const config = useLangfuseConfig()

  if (!config.data?.enabled || !config.data.host || !traceId) return null

  const url = `${config.data.host}/trace/${traceId}`

  return (
    <Tooltip title="在 Langfuse 中查看完整 Trace">
      <Button
        type="link"
        size={size}
        icon={<LinkOutlined />}
        href={url}
        target="_blank"
        rel="noopener noreferrer"
      >
        Langfuse Trace
      </Button>
    </Tooltip>
  )
}
