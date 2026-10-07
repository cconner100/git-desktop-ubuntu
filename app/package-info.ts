import { bundleID, companyName, productName, version } from './package.json'

export function getProductName() {
  const platformProductName =
    process.platform === 'linux' ? 'Git Desktop' : productName
  return process.env.NODE_ENV === 'development'
    ? `${platformProductName}-dev`
    : platformProductName
}

export function getCompanyName() {
  return companyName
}

export function getVersion() {
  return version
}

export function getBundleID() {
  return process.env.NODE_ENV === 'development' ? `${bundleID}Dev` : bundleID
}
