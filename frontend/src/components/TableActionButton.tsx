import { Button } from 'antd'
import type { ButtonProps } from 'antd'

export function TableActionButton({
  danger,
  className,
  ...props
}: ButtonProps) {
  return (
    <Button
      {...props}
      type="text"
      size="small"
      className={`tableActionButton ${danger ? 'danger' : 'primary'}${className ? ` ${className}` : ''}`}
    />
  )
}
