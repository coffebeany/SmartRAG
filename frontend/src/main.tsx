import React, { useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider, App as AntApp } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import { getErrorMessage } from './utils/errorMessage'
import { setGlobalMessageApi, showGlobalError } from './utils/globalErrorHandler'
import './styles.css'

const mutationCache = new MutationCache({
  onError: (error) => {
    showGlobalError(getErrorMessage(error))
  },
})

const queryCache = new QueryCache({
  onError: (error) => {
    showGlobalError(getErrorMessage(error, '数据加载失败，请稍后重试'))
  },
})

const queryClient = new QueryClient({
  queryCache,
  mutationCache,
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

function GlobalMessageSetup() {
  const { message } = AntApp.useApp()
  useEffect(() => {
    setGlobalMessageApi(message)
  }, [message])
  return null
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN}>
      <AntApp>
        <GlobalMessageSetup />
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
)
