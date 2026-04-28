import { Empty, Typography } from 'antd'

const METRIC_LABELS: Record<string, string> = {
  context_precision: 'Context Precision',
  context_recall: 'Context Recall',
  faithfulness: 'Faithfulness',
  answer_relevancy: 'Answer Relevancy',
  'source_chunk_hit@3': 'Hit@3',
  'source_chunk_hit@5': 'Hit@5',
  'source_chunk_hit@10': 'Hit@10',
  source_chunk_recall: 'Source Recall',
  source_chunk_mrr: 'Source MRR',
  source_chunk_rank: 'Source Rank',
}

function formatMetricValue(metricId: string, value: number) {
  if (metricId === 'source_chunk_rank') {
    return Number.isInteger(value) ? `#${value}` : `#${value.toFixed(1)}`
  }
  return value.toFixed(3)
}

export function MetricScoreGrid({ scores, compact = false }: { scores?: Record<string, number>; compact?: boolean }) {
  const entries = Object.entries(scores ?? {}).filter(([, value]) => Number.isFinite(Number(value)))
  if (!entries.length) {
    return compact ? <Typography.Text type="secondary">暂无分数</Typography.Text> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无分数" />
  }

  return (
    <div className={compact ? 'metricGrid compact' : 'metricGrid'}>
      {entries.map(([key, value]) => (
        <div className="metricTile" key={key}>
          <span className="metricName">{METRIC_LABELS[key] ?? key}</span>
          <strong>{formatMetricValue(key, Number(value))}</strong>
        </div>
      ))}
    </div>
  )
}
