using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"-9f4s92o8NRU","alg":"RS256","n":"1fpMJMO7DmZPLP57BVgWx6BSHFCTXMhf9ZwVr2ixERn-qMQ_","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"-9f4s92o8NRU\",\"alg\":\"RS256\",\"n\":\"1fpMJMO7DmZPLP57BVgWx6BSHFCTXMhf9ZwVr2ixERn-qMQ_\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
