import { App, Button, Card, Col, Descriptions, Row, Space, Table, Tabs, Tag, Typography, Upload } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { UploadFile } from 'antd/es/upload/interface'
import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  useMaterialBatch,
  useMaterialFiles,
  useMaterialVersions,
  useParserStrategies,
  useRemoveMaterialFile,
  useUploadMaterialFiles,
} from '../api/hooks'
import type { MaterialBatchVersion, MaterialFile } from '../api/types'

export default function MaterialBatchDetailPage() {
  const { batchId } = useParams()
  const { message, modal } = App.useApp()
  const [uploadList, setUploadList] = useState<UploadFile[]>([])
  const batch = useMaterialBatch(batchId)
  const files = useMaterialFiles(batchId)
  const versions = useMaterialVersions(batchId)
  const parsers = useParserStrategies()
  const uploadFiles = useUploadMaterialFiles(batchId)
  const removeFile = useRemoveMaterialFile(batchId)

  const supportedExts = useMemo(
    () => Array.from(new Set((parsers.data ?? []).flatMap((parser) => parser.supported_file_exts))).sort(),
    [parsers.data],
  )
  const accept = supportedExts.join(',')
  const isSupportedFile = (file: UploadFile) => {
    const name = file.name ?? ''
    const ext = name.includes('.') ? `.${name.split('.').pop()?.toLowerCase()}` : ''
    return supportedExts.includes(ext)
  }

  const fileColumns: ColumnsType<MaterialFile> = useMemo(
    () => [
      { title: '文件名', dataIndex: 'original_filename' },
      { title: '类型', dataIndex: 'file_ext', render: (value) => <Tag>{value || 'none'}</Tag> },
      { title: '大小', dataIndex: 'size_bytes', render: (value) => `${(value / 1024).toFixed(1)} KB` },
      { title: '状态', dataIndex: 'status', render: (value) => <Tag color={value === 'active' ? 'green' : 'default'}>{value}</Tag> },
      { title: 'Checksum', dataIndex: 'checksum', render: (value) => <Typography.Text code>{value.slice(0, 12)}</Typography.Text> },
      {
        title: '操作',
        render: (_, record) => record.status === 'active' && (
          <Button
            danger
            onClick={() => modal.confirm({
              title: '逻辑删除文件',
              content: `确认从当前批次版本中移除 ${record.original_filename}？历史版本仍可复现。`,
              onOk: () => removeFile.mutate(record.file_id, { onSuccess: () => message.success('文件已移除并生成新版本') }),
            })}
          >
            删除
          </Button>
        ),
      },
    ],
    [message, modal, removeFile],
  )

  const versionColumns: ColumnsType<MaterialBatchVersion> = useMemo(
    () => [
      { title: '版本', dataIndex: 'version_number', render: (value) => <Tag>v{value}</Tag> },
      { title: '变更', dataIndex: 'change_type' },
      { title: '新增', dataIndex: 'added_file_ids', render: (value: string[]) => value.length },
      { title: '删除', dataIndex: 'removed_file_ids', render: (value: string[]) => value.length },
      { title: '快照文件数', dataIndex: 'active_file_ids_snapshot', render: (value: string[]) => value.length },
      { title: '创建时间', dataIndex: 'created_at', render: (value) => new Date(value).toLocaleString() },
    ],
    [],
  )

  const doUpload = () => {
    const filesToUpload = uploadList.map((item) => item.originFileObj).filter(Boolean) as File[]
    uploadFiles.mutate(filesToUpload, {
      onSuccess: (result) => {
        message.success(`已上传 ${result.files.length} 个文件，生成 v${result.version.version_number}`)
        setUploadList([])
      },
    })
  }

  return (
    <Space direction="vertical" size={16} className="pageStack">
      <Row justify="space-between" align="middle">
        <Col>
          <Typography.Title level={3}>{batch.data?.batch_name ?? '批次详情'}</Typography.Title>
          <Typography.Text type="secondary">
            <Link to="/config/materials/batches">返回批次列表</Link>
          </Typography.Text>
        </Col>
      </Row>
      <Card loading={batch.isLoading}>
        {batch.data && (
          <Descriptions column={4}>
            <Descriptions.Item label="当前版本">v{batch.data.current_version}</Descriptions.Item>
            <Descriptions.Item label="文件数">{batch.data.file_count}</Descriptions.Item>
            <Descriptions.Item label="Batch ID">{batch.data.batch_id}</Descriptions.Item>
            <Descriptions.Item label="更新时间">{new Date(batch.data.updated_at).toLocaleString()}</Descriptions.Item>
          </Descriptions>
        )}
      </Card>
      <Card>
        <Upload.Dragger
          multiple
          accept={accept}
          fileList={uploadList}
          beforeUpload={() => false}
          onChange={({ fileList }) => {
            const unsupported = fileList.filter((file) => !isSupportedFile(file))
            if (unsupported.length > 0) {
              message.error(`含有不支持的文件类型：${unsupported.map((file) => file.name).join('、')}，已取消本次选择。`)
              setUploadList([])
              return
            }
            setUploadList(fileList)
          }}
        >
          <p className="ant-upload-text">拖拽或点击选择文件</p>
          <p className="ant-upload-hint">
            仅支持后端已注册 parser 的文件类型：{supportedExts.join('、') || '加载中'}。上传后会写入本地存储，并生成新的批次快照版本。
          </p>
        </Upload.Dragger>
        <Button
          type="primary"
          className="uploadAction"
          disabled={uploadList.length === 0}
          loading={uploadFiles.isPending}
          onClick={doUpload}
        >
          上传并创建版本
        </Button>
      </Card>
      <Tabs
        items={[
          {
            key: 'files',
            label: '文件列表',
            children: <Table rowKey="file_id" loading={files.isLoading} columns={fileColumns} dataSource={files.data ?? []} />,
          },
          {
            key: 'versions',
            label: '版本历史',
            children: <Table rowKey="batch_version_id" loading={versions.isLoading} columns={versionColumns} dataSource={versions.data ?? []} />,
          },
        ]}
      />
    </Space>
  )
}
