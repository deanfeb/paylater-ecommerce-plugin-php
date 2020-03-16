<?php

namespace IndodanaCommon;

use IndodanaCommon\IndodanaLogger;

class MerchantResponse
{
  private static function printResponse($response, $namespace)
  {
    IndodanaLogger::log(
      IndodanaLogger::INFO,
      sprintf(
        '%s Response: %s',
        $namespace,
        json_encode($response)
      )
    );

    header('Content-type: application/json');

    echo json_encode($response);
  }

  public static function printSuccessResponse($namespace)
  {
    return self::printResponse(
      [
        'status'  => 'OK',
        'message' => 'OK'
      ],
      $namespace
    );
  }

  public static function printInvalidRequestAuthResponse($namespace)
  {
    return self::printResponse(
      [
        'status'  => 'REJECTED',
        'message' => 'Invalid request authorization'
      ],
      $namespace
    );
  }

  public static function printInvalidRequestBodyResponse($namespace)
  {
    return self::printResponse(
      [
        'status'  => 'REJECTED',
        'message' => 'Invalid request body'
      ],
      $namespace
    );
  }

  public static function printNotFoundOrderResponse($order_id, $namespace)
  {
    return self::printResponse(
      [
        'status'  => 'REJECTED',
        'message' => "Order not found for merchant order id: ${order_id}"
      ],
      $namespace
    );
  }

  public static function printMissingOrderStatusResponse($order_id, $namespace)
  {
    return self::printResponse(
      [
        'status'  => 'REJECTED',
        'message' => "Order status is missing for merchant order id: ${order_id}"
      ],
      $namespace
    );
  }

  public static function printInvalidTransactionStatusResponse($transaction_status, $order_id, $namespace) {
    return self::printResponse(
      [
        'status'  => 'REJECTED',
        'message' => "Invalid transaction status: ${transaction_status} for merchant order id: ${order_id}"
      ],
      $namespace
    );
  }
}
